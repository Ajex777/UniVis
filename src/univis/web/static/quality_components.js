(function () {
  const h = React.createElement;
  const { useEffect, useMemo, useRef, useState } = React;
  const QualityIO = window.UniVisQualityIO;
  const { fetchJson } = window.UniVisApi;
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
  };

  function QualityPanel(props) {
    const state = props.dtwState || {};
    const expanded = !!state.expanded;
    const enabled = !!state.enabled;
    const referenceId = state.referenceId || "";
    const referenceTitle = state.referenceTitle || "";
    const [referenceTrajectory, setReferenceTrajectory] = useState(null);
    const [comparison, setComparison] = useState(null);
    const [message, setMessage] = useState("");
    const [stats, setStats] = useState(null);
    const sourceRevisionRef = useRef(props.sourceRevision);

    const referenceLabel = useMemo(() => {
      if (!referenceId) return "未选择 reference";
      return referenceTitle || referenceId;
    }, [referenceId, referenceTitle]);

    useEffect(() => {
      if (sourceRevisionRef.current === props.sourceRevision) return;
      sourceRevisionRef.current = props.sourceRevision;
      setReferenceTrajectory(null);
      setComparison(null);
      setStats(null);
      props.onOverlayChange(null);
    }, [props.sourceRevision]);

    useEffect(() => {
      if (!enabled || !referenceId || !props.episodeId) {
        props.onOverlayChange(null);
        return;
      }
      let cancelled = false;
      Promise.all([
        QualityIO.compareDTW(props.episodeId, referenceId),
        fetchJson(`/api/episodes/${referenceId}/trajectory`),
      ]).then(([result, refTraj]) => {
        if (cancelled) return;
        setComparison(result);
        setReferenceTrajectory(refTraj);
        props.onOverlayChange({
          enabled: true,
          comparison: result,
          referenceTrajectory: refTraj,
        });
      }).catch((error) => {
        if (cancelled) return;
        setMessage(error.message);
        props.onOverlayChange(null);
      });
      return () => { cancelled = true; };
    }, [enabled, referenceId, props.episodeId, props.sourceRevision]);

    function setCurrentReference() {
      const item = props.episodes.find((episode) => episode.episode_id === props.episodeId);
      props.onDtwState({
        ...state,
        referenceId: props.episodeId,
        referenceTitle: item?.title || props.episodeId,
      });
      setMessage(`已成功将 ${item?.title || props.episodeId} 作为 reference 轨迹，所有轨迹将与该轨迹进行 dynamic time warping 对比。`);
    }

    async function computeSelectedStats() {
      if (!referenceId || !props.selectedIds.size) return;
      try {
        setStats(await QualityIO.selectedStats(referenceId, [...props.selectedIds]));
      } catch (error) {
        setMessage(error.message);
      }
    }

    const headerText = !enabled ? "DTW · 未启用" : `DTW · ${referenceLabel}`;
    return h(React.Fragment, null,
      h("div", { className: "quality-card" },
        h("button", {
          className: "quality-header",
          onClick: () => props.onDtwState({ ...state, expanded: !expanded }),
        },
          h("strong", null, headerText),
          h("span", null, expanded ? "Collapse" : "Expand"),
        ),
        expanded ? h("div", { className: "quality-body" },
          h("label", { className: "checkbox-label" },
            h("input", {
              type: "checkbox",
              checked: enabled,
              onChange: (event) => props.onDtwState({ ...state, enabled: event.target.checked }),
            }),
            " Enable DTW",
          ),
          h("p", { className: "meta" }, `Reference: ${referenceLabel}`),
          h("button", { className: "primary", onClick: setCurrentReference, disabled: !props.episodeId }, "Use current as reference"),
          h("button", {
            className: "ghost",
            onClick: computeSelectedStats,
            disabled: !referenceId || !props.selectedIds.size,
          }, props.selectedIds.size ? `Compute selected stats (${props.selectedIds.size})` : "Compute selected stats"),
          message ? h("p", { className: "quality-message" }, message) : null,
        ) : null,
      ),
      enabled && comparison ? h(DTWMetricsPopup, { comparison, currentTitle: props.currentTitle, referenceTitle }) : null,
      stats ? h(SelectedStatsPopup, { stats, onClose: () => setStats(null) }) : null,
    );
  }

  function DTWMetricsPopup({ comparison, currentTitle, referenceTitle }) {
    const [pos, setPos] = useState(defaultMetricsPopupPosition);
    return h("div", {
      className: "dtw-popup",
      style: { left: pos.x, top: pos.y },
      onMouseDown: (event) => startDrag(event, pos, setPos),
    },
      h("strong", null, "DTW Metrics"),
      h("p", { className: "meta" }, `${currentTitle || comparison.current_episode_id} vs ${referenceTitle || comparison.reference_episode_id}`),
      h(MetricBlock, { title: "Left", summary: comparison.left.summary }),
      h(MetricBlock, { title: "Right", summary: comparison.right.summary }),
    );
  }

  function defaultMetricsPopupPosition() {
    const target = document.getElementById("trajectory-plot");
    if (!target) return { x: 420, y: 18 };
    const rect = target.getBoundingClientRect();
    return {
      x: Math.max(12, rect.left + 16),
      y: Math.max(12, rect.top + 16),
    };
  }

  function MetricBlock({ title, summary }) {
    return h("div", { className: "metric-block" },
      h("strong", null, title),
      h(MetricItem, { label: "DTW", value: summary.dtw_cost_normalized.toFixed(3), helpKey: "dtw_cost_normalized" }),
      h(MetricItem, { label: "pos mean", value: summary.mean_position_error.toFixed(4), helpKey: "mean_position_error" }),
      h(MetricItem, { label: "pos p95", value: summary.p95_position_error.toFixed(4), helpKey: "p95_position_error" }),
      h(MetricItem, { label: "rot mean", value: `${summary.mean_rotation_error_deg.toFixed(2)}°`, helpKey: "mean_rotation_error_deg" }),
      h(MetricItem, { label: "warp", value: summary.warp_distortion.toFixed(3), helpKey: "warp_distortion" }),
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

  function StatsSummary({ title, summary }) {
    return h("div", { className: "metric-block" },
      h("strong", null, title),
      h(MetricItem, { label: "DTW mean", value: formatMaybe(summary.dtw_cost_normalized_mean, 3), helpKey: "dtw_cost_normalized_mean" }),
      h(MetricItem, { label: "DTW p95", value: formatMaybe(summary.dtw_cost_normalized_p95, 3), helpKey: "dtw_cost_normalized_p95" }),
      h(MetricItem, { label: "pos p95 mean", value: formatMaybe(summary.p95_position_error_mean, 4), helpKey: "p95_position_error_mean" }),
      h(MetricItem, { label: "rot p95 mean", value: `${formatMaybe(summary.p95_rotation_error_deg_mean, 2)}°`, helpKey: "p95_rotation_error_deg_mean" }),
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

  window.UniVisQualityComponents = { QualityPanel };
})();
