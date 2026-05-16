(function () {
  const { fetchJson } = window.UniVisApi;

  /**
   * Convert one active episode through a registered exporter.
   * Input: episode id, exporter name, and optional output root.
   * Output: Conversion report payload.
   */
  function convertEpisode(episodeId, exporterName, outputRoot) {
    return fetchJson(`/api/conversions/episodes/${episodeId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ exporter_name: exporterName, output_root: outputRoot || "" }),
    });
  }

  /**
   * Convert all accepted episodes from the active source.
   * Input: exporter name and optional output root.
   * Output: Conversion report payload.
   */
  function convertAccepted(exporterName, outputRoot) {
    return fetchJson("/api/conversions/accepted", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ exporter_name: exporterName, output_root: outputRoot || "" }),
    });
  }

  function listJobs() {
    return fetchJson("/api/conversions/jobs");
  }

  window.UniVisConversionIO = { convertAccepted, convertEpisode, listJobs };
})();
