# Codex Usage Monitor for Waybar

A Waybar custom module that displays your Codex 5-hour and weekly rate-limit usage, plus the 5-hour reset countdown.

Default display:

```text
5H 22% · W 18% · 2h55m
```

It reads usage through the installed Codex CLI's `account/rateLimits/read` app-server method. It does not read or transmit raw authentication tokens.

## Requirements

- Codex CLI logged in with ChatGPT
- Python 3.11 or newer
- Waybar with custom module support

## Install

Install the commands without changing Waybar:

```bash
./install.sh
```

Install and configure the module in a selected Waybar section:

```bash
./install.sh --configure-waybar --section right --restart
```

The configurator backs up `config.jsonc` and `style.css`, preserves JSONC comments, avoids duplicate module entries, and aborts if it cannot identify the requested module section safely.

## Manual Waybar Setup

Add `custom/codex-usage` to any one of `modules-left`, `modules-center`, or `modules-right`.

Add this module definition to `~/.config/waybar/config.jsonc`:

```jsonc
"custom/codex-usage": {
  "exec": "codex-waybar",
  "return-type": "json",
  "interval": 60,
  "tooltip": true
}
```

Then restart Waybar:

```bash
omarchy restart waybar
```

## Formatting

Formatting is configured in Waybar's `exec` command, like other custom module command options:

```jsonc
"custom/codex-usage": {
  "exec": "codex-waybar --format '5H {five_hour_used}% | W {weekly_used}% | {five_hour_reset_in}'",
  "return-type": "json",
  "interval": 60
}
```

Available placeholders:

| Placeholder | Meaning |
| --- | --- |
| `{five_hour_used}` | 5-hour usage percentage |
| `{weekly_used}` | Weekly usage percentage |
| `{five_hour_reset_in}` | Time remaining until the 5-hour reset |
| `{weekly_reset_in}` | Time remaining until the weekly reset |
| `{five_hour_reset_at}` | Local 5-hour reset date and time |
| `{weekly_reset_at}` | Local weekly reset date and time |
| `{plan}` | ChatGPT plan reported by Codex |

Other command options:

```text
--tooltip-format TEMPLATE
--warning PERCENT       default: 70
--critical PERCENT      default: 90
--timeout SECONDS       default: 10
--no-cache
```

## Styling

The command emits these Waybar CSS classes:

- `normal`
- `warning`
- `critical`
- `stale`: the live refresh failed and cached data is displayed
- `unavailable`: no live or cached data is available

Example:

```css
#custom-codex-usage {
  margin: 0 7.5px;
}

#custom-codex-usage.warning {
  color: #d8a657;
}

#custom-codex-usage.critical,
#custom-codex-usage.unavailable {
  color: #a55555;
}

#custom-codex-usage.stale {
  opacity: 0.65;
}
```

## Troubleshooting

Run the module directly. It always prints Waybar-compatible JSON:

```bash
codex-waybar | jq
```

If it reports unavailable usage, confirm that `codex` is installed and logged in:

```bash
codex login status
```

The last valid response is cached at `${XDG_CACHE_HOME:-~/.cache}/codex-waybar/rate-limits.json`. The cache contains rate-limit percentages and reset timestamps, not credentials.

## Development

Run the tests:

```bash
python -m unittest discover -s tests -v
```

Run directly from the repository:

```bash
./bin/codex-waybar | jq
```

## Uninstall

Remove the installed commands:

```bash
rm ~/.local/bin/codex-waybar ~/.local/bin/codex-waybar-configure
```

Remove `custom/codex-usage` from your Waybar module list and module definition, then remove its CSS rules.
