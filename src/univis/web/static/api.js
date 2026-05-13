(function () {
  /**
   * Fetch JSON from the API.
   * Input: URL and optional fetch options.
   * Output: Parsed JSON payload or an exception for failed responses.
   */
  async function fetchJson(url, options) {
    const response = await fetch(url, options);
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
    return response.json();
  }

  /**
   * Return the image URL for a generated camera frame.
   * Input: episode id, camera key, and frame index.
   * Output: API URL string for an SVG image.
   */
  function frameUrl(episodeId, cameraKey, frameIndex) {
    return `/api/episodes/${episodeId}/frame/${cameraKey}/${frameIndex}`;
  }

  window.UniVisApi = { fetchJson, frameUrl };
})();
