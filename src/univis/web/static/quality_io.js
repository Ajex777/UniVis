(function () {
  const { fetchJson } = window.UniVisApi;

  /**
   * Compare current and reference episodes with DTW.
   * Input: current episode id and reference episode id.
   * Output: EpisodeDTWComparison payload.
   */
  function compareDTW(currentEpisodeId, referenceEpisodeId) {
    return fetchJson("/api/quality/dtw/compare", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        current_episode_id: currentEpisodeId,
        reference_episode_id: referenceEpisodeId,
      }),
    });
  }

  /**
   * Compute selected episode statistics against one reference.
   * Input: reference episode id and selected episode ids.
   * Output: SelectedEpisodeDTWStats payload.
   */
  function selectedStats(referenceEpisodeId, episodeIds) {
    return fetchJson("/api/quality/dtw/selected-stats", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        reference_episode_id: referenceEpisodeId,
        episode_ids: episodeIds,
      }),
    });
  }

  /**
   * Assess one episode's reference-free trajectory smoothness.
   * Input: current episode id.
   * Output: EpisodeSmoothnessReport payload.
   */
  function assessSmoothness(episodeId) {
    return fetchJson("/api/quality/smooth/episode", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ episode_id: episodeId }),
    });
  }

  window.UniVisQualityIO = { compareDTW, selectedStats, assessSmoothness };
})();
