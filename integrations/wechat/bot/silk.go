package bot

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"strconv"
	"time"
)

// WeChat voice is SILK-v3 at 24 kHz mono; matching the decoder's API rate
// avoids a needless resample, and lame must be told the same rate.
const silkSampleRate = 24000

// 60s voice clips transcode in well under a second; cap each step at 10s.
const silkTranscodeTimeout = 10 * time.Second

// 32 kbps mono is intelligible for voice and ~12x smaller than raw PCM.
const mp3Bitrate = "32"

// transcodeSilkToMP3 shells out to silk_v3_decoder + lame to convert a
// WeChat-flavoured SILK-v3 payload to MP3. Both binaries are installed by
// Dockerfile.wechat; if either is missing the wrapped exec error makes that
// obvious to the caller, who can fall back to uploading the raw SILK.
func transcodeSilkToMP3(ctx context.Context, silk []byte) ([]byte, error) {
	if len(silk) == 0 {
		return nil, errors.New("silk payload is empty")
	}

	silkPath, cleanupSilk, err := writeTempFile("wechat-voice-*.silk", silk)
	if err != nil {
		return nil, err
	}
	defer cleanupSilk()

	pcmPath, cleanupPCM, err := writeTempFile("wechat-voice-*.pcm", nil)
	if err != nil {
		return nil, err
	}
	defer cleanupPCM()

	rate := strconv.Itoa(silkSampleRate)
	if _, err := runCmd(ctx, "silk_v3_decoder", silkPath, pcmPath, "-Fs_API", rate, "-quiet"); err != nil {
		return nil, err
	}

	// silk_v3_decoder exits 0 on bad input (printing "Error: ..." to stdout
	// rather than returning a non-zero status), so the exit code can't be
	// trusted. An empty PCM file is the reliable signal of decode failure.
	if info, err := os.Stat(pcmPath); err != nil {
		return nil, fmt.Errorf("stat pcm: %w", err)
	} else if info.Size() == 0 {
		return nil, errors.New("silk_v3_decoder produced empty pcm (invalid silk input)")
	}

	// lame reads raw s16le PCM matching silk_v3_decoder's output and writes
	// MP3 to stdout via "-".
	mp3, err := runCmd(ctx, "lame",
		"-r", "--signed", "--little-endian",
		"-s", strconv.Itoa(silkSampleRate/1000),
		"-m", "m", "-b", mp3Bitrate,
		"--silent",
		pcmPath, "-",
	)
	if err != nil {
		return nil, err
	}
	if len(mp3) == 0 {
		return nil, errors.New("lame produced empty output")
	}
	return mp3, nil
}

// writeTempFile creates a uniquely-named temp file, optionally writes data
// to it, and returns the path plus a cleanup func. Pass nil data to reserve
// the path for a subprocess to fill in.
func writeTempFile(pattern string, data []byte) (string, func(), error) {
	f, err := os.CreateTemp("", pattern)
	if err != nil {
		return "", nil, fmt.Errorf("create temp %s: %w", pattern, err)
	}
	cleanup := func() { os.Remove(f.Name()) }
	if data != nil {
		if _, err := f.Write(data); err != nil {
			f.Close()
			cleanup()
			return "", nil, fmt.Errorf("write temp %s: %w", pattern, err)
		}
	}
	if err := f.Close(); err != nil {
		cleanup()
		return "", nil, fmt.Errorf("close temp %s: %w", pattern, err)
	}
	return f.Name(), cleanup, nil
}

func runCmd(ctx context.Context, name string, args ...string) ([]byte, error) {
	cctx, cancel := context.WithTimeout(ctx, silkTranscodeTimeout)
	defer cancel()
	cmd := exec.CommandContext(cctx, name, args...)
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr
	if err := cmd.Run(); err != nil {
		// silk_v3_decoder writes errors to stdout, lame writes them to
		// stderr — surface both so failure mode is debuggable regardless.
		return nil, fmt.Errorf("%s: %w (stdout: %s, stderr: %s)",
			name, err, truncate(stdout.String(), 256), truncate(stderr.String(), 256))
	}
	return stdout.Bytes(), nil
}

func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n] + "…"
}
