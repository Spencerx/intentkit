package bot

import (
	"context"
	"strings"
	"testing"
)

func TestTranscodeSilkToMP3_EmptyInput(t *testing.T) {
	_, err := transcodeSilkToMP3(context.Background(), nil)
	if err == nil {
		t.Fatal("expected error for empty silk payload, got nil")
	}
	if !strings.Contains(err.Error(), "empty") {
		t.Fatalf("expected empty-payload error, got %v", err)
	}
}

func TestTranscodeSilkToMP3_MissingBinary(t *testing.T) {
	t.Setenv("PATH", "/nonexistent")
	_, err := transcodeSilkToMP3(context.Background(), []byte{0x02, '#', '!', 'S', 'I', 'L', 'K', '_', 'V', '3'})
	if err == nil {
		t.Fatal("expected error when silk_v3_decoder is not on PATH")
	}
	if !strings.Contains(err.Error(), "silk_v3_decoder") {
		t.Fatalf("expected silk_v3_decoder error, got %v", err)
	}
}
