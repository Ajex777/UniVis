(function () {
  const h = React.createElement;
  const { useState } = React;
  const METRIC_HELP = {
    dtw_cost_normalized: "归一化 DTW cost。它是 DTW 总 cost 除以对齐路径长度，更适合比较不同长度的轨迹；数值越小表示越接近 reference。",
    mean_position_error: "平均位置误差。DTW 匹配点之间 EEF 位置距离的平均值，单位是米。",
    p95_position_error: "95 分位位置误差。95% 的 DTW 匹配点位置误差都不超过该值，单位是米。",
    mean_rotation_error_deg: "平均旋转误差。DTW 匹配点之间 rot6d 转 rotation matrix 后的 geodesic 角度误差平均值，单位是度。",
    warp_distortion: "时间扭曲程度。表示 DTW 为了对齐两条轨迹需要多强的时间拉伸；越大说明执行节奏差异越明显。",
    dtw_cost_normalized_mean: "所有 selected episode 的归一化 DTW cost 平均值；数值越小表示整体越接近 reference。",
    dtw_cost_normalized_p95: "所有 selected episode 的归一化 DTW cost 的 95 分位；用于观察大多数 episode 中较差的一批是否仍可接受。",
    p95_position_error_mean: "先计算每条 episode 自己的 p95 位置误差，再对这些 p95 值取平均，单位是米。",
    p95_rotation_error_deg_mean: "先计算每条 episode 自己的 p95 旋转误差，再对这些 p95 值取平均，单位是度。",
    acceleration_cost: "加速度平滑代价。基于 EEF 位置二阶差分计算，数值越大通常表示动作越急或越抖。",
    jerk_cost: "Jerk 平滑代价。基于 EEF 位置三阶差分计算，数值越大通常表示轨迹存在突变或不连续。",
  };

  function DTWMetricsPopup({ comparison, currentTitle, referenceTitle }) {
    const [pos, setPos] = useState(() => defaultQualityPopupPosition(16));
    return h("div", {
      className: "quality-popup dtw-popup",
      style: { left: pos.x, top: pos.y },
      onMouseDown: (event) => startDrag(event, pos, setPos),
    },
      h("strong", null, "DTW Metrics"),
      h("p", { className: "meta" }, `${currentTitle || comparison.current_episode_id} vs ${referenceTitle || comparison.reference_episode_id}`),
      h(DTWMetricBlock, { title: "Left", summary: comparison.left.summary }),
      h(DTWMetricBlock, { title: "Right", summary: comparison.right.summary }),
    );
  }

  function SmoothMetricsPopup({ report }) {
    const [pos, setPos] = useState(() => defaultQualityPopupPosition(264));
    return h("div", {
      className: "quality-popup smooth-popup",
      style: { left: pos.x, top: pos.y },
      onMouseDown: (event) => startDrag(event, pos, setPos),
    },
      h("strong", null, `Smooth Metrics · ${report.passed ? "Passed" : "Warning"}`),
      h("p", { className: "meta" }, `${report.episode_id} · ${report.num_frames} frames`),
      h(SmoothnessReport, { report }),
    );
  }

  function SelectedStatsPopup({ stats, onClose }) {
    return h("div", { className: "stats-modal" },
      h("div", { className: "stats-box" },
        h("div", { className: "record-line" },
          h("strong", null, "Selected DTW Stats"),
          h("button", { className: "ghost", onClick: onClose }, "Close"),
        ),
        h("p", { className: "meta" }, `Reference: ${stats.reference_episode_id}`),
        h(StatsSummary, { title: "Left", summary: stats.left_summary }),
        h(StatsSummary, { title: "Right", summary: stats.right_summary }),
        h("strong", null, "Top abnormal"),
        stats.abnormal_episodes.map((item) =>
          h("p", { key: item.episode_id, className: "meta" },
            `${item.episode_id}: L ${item.left_dtw_cost_normalized.toFixed(3)} / R ${item.right_dtw_cost_normalized.toFixed(3)}`,
          ),
        ),
      ),
    );
  }

  function DTWMetricBlock({ title, summary }) {
    return h("div", { className: "metric-block" },
      h("strong", null, title),
      h(MetricItem, { label: "DTW", value: summary.dtw_cost_normalized.toFixed(3), helpKey: "dtw_cost_normalized" }),
      h(MetricItem, { label: "pos mean", value: summary.mean_position_error.toFixed(4), helpKey: "mean_position_error" }),
      h(MetricItem, { label: "pos p95", value: summary.p95_position_error.toFixed(4), helpKey: "p95_position_error" }),
      h(MetricItem, { label: "rot mean", value: `${summary.mean_rotation_error_deg.toFixed(2)}°`, helpKey: "mean_rotation_error_deg" }),
      h(MetricItem, { label: "warp", value: summary.warp_distortion.toFixed(3), helpKey: "warp_distortion" }),
    );
  }

  function StatsSummary({ title, summary }) {
    return h("div", { className: "metric-block" },
      h("strong", null, title),
      h(MetricItem, { label: "DTW mean", value: formatMaybe(summary.dtw_cost_normalized_mean, 3), helpKey: "dtw_cost_normalized_mean" }),
      h(MetricItem, { label: "DTW p95", value: formatMaybe(summary.dtw_cost_normalized_p95, 3), helpKey: "dtw_cost_normalized_p95" }),
      h(MetricItem, { label: "pos p95 mean", value: formatMaybe(summary.p95_position_error_mean, 4), helpKey: "p95_position_error_mean" }),
      h(MetricItem, { label: "rot p95 mean", value: `${formatMaybe(summary.p95_rotation_error_deg_mean, 2)}°`, helpKey: "p95_rotation_error_deg_mean" }),
    );
  }

  function SmoothnessReport({ report }) {
    const scopes = Object.entries(report.scopes || {});
    return h("div", { className: "smooth-report" },
      scopes.map(([name, summary]) =>
        h("div", { key: name, className: "metric-block smooth-scope" },
          h("strong", null, `${name} · ${summary.passed ? "passed" : "warning"}`),
          h(MetricItem, { label: "acc cost", value: summary.acceleration_cost.toFixed(3), helpKey: "acceleration_cost" }),
          h(MetricItem, { label: "jerk cost", value: summary.jerk_cost.toFixed(3), helpKey: "jerk_cost" }),
          h(MetricItem, { label: "max acc", value: summary.max_acceleration.toFixed(3), helpKey: "acceleration_cost" }),
          h(MetricItem, { label: "max jerk", value: summary.max_jerk.toFixed(3), helpKey: "jerk_cost" }),
          summary.warnings?.length ? h("p", { className: "quality-message smooth-warning" }, summary.warnings.join("; ")) : null,
        ),
      ),
    );
  }

  function MetricItem({ label, value, helpKey }) {
    return h("span", { className: "metric-item" },
      h("span", { className: "metric-label" },
        label,
        h("span", {
          className: "metric-help",
          "data-tooltip": METRIC_HELP[helpKey] || "暂无说明",
          "aria-label": METRIC_HELP[helpKey] || "暂无说明",
        }, "?"),
      ),
      h("span", { className: "metric-value" }, value),
    );
  }

  function defaultQualityPopupPosition(offsetY) {
    const target = document.getElementById("trajectory-plot");
    if (!target) return { x: 420, y: Math.max(18, offsetY) };
    const rect = target.getBoundingClientRect();
    return {
      x: Math.max(12, rect.left + 16),
      y: Math.max(12, rect.top + offsetY),
    };
  }

  function formatMaybe(value, digits) {
    return Number.isFinite(value) ? value.toFixed(digits) : "n/a";
  }

  function startDrag(event, pos, setPos) {
    if (event.target.tagName === "BUTTON") return;
    const startX = event.clientX;
    const startY = event.clientY;
    function move(moveEvent) {
      setPos({ x: pos.x + moveEvent.clientX - startX, y: pos.y + moveEvent.clientY - startY });
    }
    function stop() {
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", stop);
    }
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", stop);
  }

  window.UniVisQualityPopups = { DTWMetricsPopup, SelectedStatsPopup, SmoothMetricsPopup };
})();
