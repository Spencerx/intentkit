package config

import (
	"fmt"
	"time"

	"github.com/hack-fan/config"

	"github.com/crestalnetwork/intentkit/integrations/shared/alert"
)

type Config struct {
	Env     string `default:"local"`
	Debug   bool   `default:"false"`
	Release string `env:"RELEASE"`

	// DB
	DBHost     string `env:"DB_HOST"`
	DBPort     string `env:"DB_PORT" default:"5432"`
	DBName     string `env:"DB_NAME"`
	DBUsername string `env:"DB_USERNAME"`
	DBPassword string `env:"DB_PASSWORD"`

	// Internal API
	InternalBaseURL string `env:"INTERNAL_BASE_URL" default:"http://intent-api"`

	// Redis (used by alert handler for shared rate limiting)
	RedisHost     string `env:"REDIS_HOST"`
	RedisPort     string `env:"REDIS_PORT" default:"6379"`
	RedisPassword string `env:"REDIS_PASSWORD"`
	RedisDB       int    `env:"REDIS_DB" default:"0"`

	// WeChat
	WxNewChannelPollInterval int `env:"WX_NEW_CHANNEL_POLL_INTERVAL" default:"10"`

	// WeChat session window — iLink only accepts proactive bot messages within
	// the customer-service window of the user's last inbound message. The raw
	// env strings are parsed into the resolved Duration fields below in Load().
	WxSessionWindowRaw     string `env:"WX_SESSION_WINDOW" default:"24h"`
	WxSessionWarnBeforeRaw string `env:"WX_SESSION_WARN_BEFORE" default:"30m"`

	WxSessionWindow     time.Duration `yaml:"-"`
	WxSessionWarnBefore time.Duration `yaml:"-"`

	// Alert (forwards Error+ slog records to Telegram/Slack)
	Alert alert.Config
}

func Load() (*Config, error) {
	var cfg Config
	if err := config.Load(&cfg); err != nil {
		return nil, err
	}

	window, err := time.ParseDuration(cfg.WxSessionWindowRaw)
	if err != nil {
		return nil, fmt.Errorf("invalid WX_SESSION_WINDOW %q: %w", cfg.WxSessionWindowRaw, err)
	}
	warnBefore, err := time.ParseDuration(cfg.WxSessionWarnBeforeRaw)
	if err != nil {
		return nil, fmt.Errorf("invalid WX_SESSION_WARN_BEFORE %q: %w", cfg.WxSessionWarnBeforeRaw, err)
	}
	if warnBefore <= 0 || warnBefore >= window {
		return nil, fmt.Errorf(
			"WX_SESSION_WARN_BEFORE (%s) must be > 0 and < WX_SESSION_WINDOW (%s)",
			warnBefore, window,
		)
	}
	cfg.WxSessionWindow = window
	cfg.WxSessionWarnBefore = warnBefore

	return &cfg, nil
}

func (c *Config) DatabaseDSN() string {
	dsn := fmt.Sprintf("host=%s dbname=%s port=%s sslmode=disable TimeZone=UTC",
		c.DBHost, c.DBName, c.DBPort)
	if c.DBUsername != "" {
		dsn += fmt.Sprintf(" user=%s", c.DBUsername)
	}
	if c.DBPassword != "" {
		dsn += fmt.Sprintf(" password=%s", c.DBPassword)
	}
	return dsn
}
