"""SVG frame generation for fake camera streams."""

from __future__ import annotations

from html import escape


def make_camera_svg(
    *,
    camera_key: str,
    frame_index: int,
    width: int,
    height: int,
    color: str,
    total_frames: int,
) -> str:
    """Build a deterministic fake camera frame as SVG.

    Inputs:
        camera_key: Camera identifier rendered in the frame.
        frame_index: Current synchronized frame index.
        width: SVG width.
        height: SVG height.
        color: Accent color.
        total_frames: Total episode frame count.
    Output:
        UTF-8 SVG string suitable for an image response.
    """

    safe_key = escape(camera_key)
    pct = 0.0 if total_frames <= 1 else frame_index / float(total_frames - 1)
    bar_w = int(max(4, width * pct))
    marker_x = int(24 + (width - 48) * pct)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#f8faf8"/>
      <stop offset="100%" stop-color="#dfe8ec"/>
    </linearGradient>
  </defs>
  <rect width="100%" height="100%" fill="url(#bg)"/>
  <rect x="18" y="18" width="{width - 36}" height="{height - 36}" rx="18" fill="none" stroke="{color}" stroke-width="5" opacity="0.72"/>
  <circle cx="{marker_x}" cy="{height // 2}" r="34" fill="{color}" opacity="0.82"/>
  <rect x="0" y="{height - 14}" width="{bar_w}" height="14" fill="{color}" opacity="0.86"/>
  <text x="32" y="58" font-size="30" font-family="monospace" fill="#1d2a32">{safe_key}</text>
  <text x="32" y="{height - 38}" font-size="24" font-family="monospace" fill="#1d2a32">frame {frame_index:03d}</text>
</svg>"""
