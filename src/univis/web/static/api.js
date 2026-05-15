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

  window.UniVisApi = { fetchJson, frameUrl };
})();
