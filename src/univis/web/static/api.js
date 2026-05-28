(function () {
  /**
   * Fetch JSON from the API.
   * Input: URL and optional fetch options.
   * Output: Parsed JSON payload or an exception for failed responses.
   */
  async function fetchJson(url, options) {
    const response = await fetch(url, options);
    if (!response.ok) {
      let detail = `${response.status} ${response.statusText}`;
      try {
        const payload = await response.json();
        detail = payload.detail || detail;
      } catch (_error) {
        detail = `${response.status} ${response.statusText}`;
      }
      throw new Error(detail);
    }
    return response.json();
  }

  function frameUrl(episodeId, cameraKey, frameIndex) {
    return `/api/episodes/${episodeId}/frame/${cameraKey}/${frameIndex}`;
  }

  /**
   * Apply one annotation to multiple episodes.
   * Input: list of episode IDs and an annotation payload.
   * Output: batch result containing per-episode status.
   */
  async function batchAnnotation(episodeIds, annotation) {
    return fetchJson("/api/episodes/batch/annotation", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ episode_ids: episodeIds, annotation }),
    });
  }

  window.UniVisApi = { fetchJson, frameUrl, batchAnnotation };
})();
