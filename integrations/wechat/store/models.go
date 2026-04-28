package store

import (
	"context"
	"encoding/json"
	"time"

	"gorm.io/datatypes"
	"gorm.io/gorm"
)

// TeamChannel represents a team's bound communication channel.
// WeChat integration only uses team channels (no individual agents).
type TeamChannel struct {
	TeamID      string            `gorm:"primaryKey"`
	ChannelType string            `gorm:"primaryKey"`
	Enabled     bool              `gorm:"default:true"`
	Config      datatypes.JSONMap `gorm:"type:jsonb"`
	UpdatedAt   time.Time
}

func (TeamChannel) TableName() string {
	return "team_channels"
}

// TeamChannelData represents runtime data for a team channel bot.
type TeamChannelData struct {
	TeamID      string            `gorm:"primaryKey"`
	ChannelType string            `gorm:"primaryKey"`
	Data        datatypes.JSONMap `gorm:"type:jsonb"`
}

func (TeamChannelData) TableName() string {
	return "team_channel_data"
}

// MergeTeamChannelDataField merges {fieldKey: value} into the JSONB
// team_channel_data.data column for (teamID, channelType), without
// trampling sibling keys. value is JSON-marshalled by this helper, so
// callers pass any type and get the same semantics as setting one key
// in the JSON document.
//
// Uses INSERT ... ON CONFLICT DO UPDATE because wechat (unlike telegram)
// does not pre-create the team_channel_data row at channel-binding time,
// so the first write for a channel must create the row.
func MergeTeamChannelDataField(
	ctx context.Context,
	db *gorm.DB,
	teamID, channelType, fieldKey string,
	value any,
) error {
	buf, err := json.Marshal(value)
	if err != nil {
		return err
	}
	return db.WithContext(ctx).Exec(
		`INSERT INTO team_channel_data (team_id, channel_type, data)
		 VALUES (?, ?, jsonb_build_object(?::text, ?::jsonb))
		 ON CONFLICT (team_id, channel_type) DO UPDATE
		   SET data = COALESCE(team_channel_data.data, '{}'::jsonb)
		     || jsonb_build_object(?::text, ?::jsonb)`,
		teamID, channelType, fieldKey, string(buf),
		fieldKey, string(buf),
	).Error
}
