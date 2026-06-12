(function () {
  const h = React.createElement;
  const { useEffect, useMemo, useRef, useState } = React;
  const QualityIO = window.UniVisQualityIO;
  const { fetchJson } = window.UniVisApi;
  const { DTWMetricsPopup, SelectedStatsPopup, SmoothMetricsPopup } = window.UniVisQualityPopups;

  function QualityPanel(props) {
    const state = props.dtwState || {};
    const smoothState = props.smoothState || {};
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
      props.onSmoothState({ expanded: false, report: null, message: "" });
      props.onOverlayChange(null);
    }, [props.sourceRevision]);

    useEffect(() => {
      props.onSmoothState({ ...smoothState, report: null, message: "" });
    }, [props.episodeId, props.sourceRevision]);

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

    async function assessSmoothness() {
      if (!props.episodeId) return;
      try {
        const report = await QualityIO.assessSmoothness(props.episodeId);
        props.onSmoothState({
          ...smoothState,
          report,
          message: report.passed ? "Smooth passed" : "Smooth warning",
        });
      } catch (error) {
        props.onSmoothState({ ...smoothState, report: null, message: error.message });
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
      h("div", { className: "quality-card" },
        h("button", {
          className: "quality-header",
          onClick: () => props.onSmoothState({ ...smoothState, expanded: !smoothState.expanded }),
        },
          h("strong", null, smoothState.report ? `Smooth · ${smoothState.report.passed ? "Passed" : "Warning"}` : "Smooth"),
          h("span", null, smoothState.expanded ? "Collapse" : "Expand"),
        ),
        smoothState.expanded ? h("div", { className: "quality-body" },
          h("button", { className: "primary", onClick: assessSmoothness, disabled: !props.episodeId }, "Assess current"),
          smoothState.message ? h("p", { className: "quality-message" }, smoothState.message) : null,
        ) : null,
      ),
      enabled && comparison ? h(DTWMetricsPopup, { comparison, currentTitle: props.currentTitle, referenceTitle }) : null,
      smoothState.report ? h(SmoothMetricsPopup, { report: smoothState.report }) : null,
      stats ? h(SelectedStatsPopup, { stats, onClose: () => setStats(null) }) : null,
    );
  }

  window.UniVisQualityComponents = { QualityPanel };
})();
