(function () {
  const h = React.createElement;
  const { useEffect, useMemo, useRef, useState } = React;
  const QualityIO = window.UniVisQualityIO;
  const { fetchJson } = window.UniVisApi;

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
    const [pos, setPos] = useState({ x: 420, y: 18 });
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

  function MetricBlock({ title, summary }) {
    return h("div", { className: "metric-block" },
      h("strong", null, title),
      h("span", null, `DTW ${summary.dtw_cost_normalized.toFixed(3)}`),
      h("span", null, `pos mean ${summary.mean_position_error.toFixed(4)}`),
      h("span", null, `pos p95 ${summary.p95_position_error.toFixed(4)}`),
      h("span", null, `rot mean ${summary.mean_rotation_error_deg.toFixed(2)}°`),
      h("span", null, `warp ${summary.warp_distortion.toFixed(3)}`),
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
      h("span", null, `DTW mean ${summary.dtw_cost_normalized_mean?.toFixed(3) || "n/a"}`),
      h("span", null, `DTW p95 ${summary.dtw_cost_normalized_p95?.toFixed(3) || "n/a"}`),
      h("span", null, `pos p95 mean ${summary.p95_position_error_mean?.toFixed(4) || "n/a"}`),
      h("span", null, `rot p95 mean ${summary.p95_rotation_error_deg_mean?.toFixed(2) || "n/a"}°`),
    );
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
