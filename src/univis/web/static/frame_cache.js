(function () {
  const { useEffect, useMemo, useRef, useState } = React;
  const { fetchJson, frameBatchUrl } = window.UniVisApi;
  const BATCH_SIZE = 50;

  function useFrameCache(episodeId, cameraKeys, frameIndex, numFrames) {
    const cacheRef = useRef(new Map());
    const inFlightRef = useRef(new Set());
    const [version, setVersion] = useState(0);
    const camerasKey = cameraKeys.join("|");

    useEffect(() => {
      return () => clearCache(cacheRef.current);
    }, [episodeId]);

    useEffect(() => {
      if (!episodeId || !numFrames || !cameraKeys.length) return undefined;
      let cancelled = false;
      const starts = windowStarts(frameIndex, numFrames);
      cameraKeys.forEach((cameraKey) => {
        starts.forEach((start) => {
          const requestKey = `${episodeId}:${cameraKey}:${start}`;
          const firstFrameKey = frameKey(episodeId, cameraKey, start);
          if (inFlightRef.current.has(requestKey) || cacheRef.current.has(firstFrameKey)) {
            return;
          }
          inFlightRef.current.add(requestKey);
          fetchJson(frameBatchUrl(episodeId, cameraKey, start, BATCH_SIZE))
            .then((payload) => {
              if (cancelled) return;
              payload.frames.forEach((frame) => {
                const key = frameKey(episodeId, cameraKey, frame.index);
                if (!cacheRef.current.has(key)) {
                  cacheRef.current.set(key, objectUrl(frame));
                }
              });
              trimCache(cacheRef.current, episodeId, cameraKeys, starts, numFrames);
              setVersion((value) => value + 1);
            })
            .finally(() => inFlightRef.current.delete(requestKey));
        });
      });
      return () => {
        cancelled = true;
      };
    }, [episodeId, camerasKey, frameIndex, numFrames]);

    return useMemo(() => {
      const urls = {};
      cameraKeys.forEach((cameraKey) => {
        urls[cameraKey] = cacheRef.current.get(frameKey(episodeId, cameraKey, frameIndex)) || "";
      });
      return urls;
    }, [episodeId, camerasKey, frameIndex, version]);
  }

  function windowStarts(frameIndex, numFrames) {
    const current = Math.floor(frameIndex / BATCH_SIZE) * BATCH_SIZE;
    const starts = [current, current + BATCH_SIZE];
    if (current > 0) starts.push(current - BATCH_SIZE);
    return starts.filter((start) => start >= 0 && start < numFrames);
  }

  function frameKey(episodeId, cameraKey, frameIndex) {
    return `${episodeId}:${cameraKey}:${frameIndex}`;
  }

  function objectUrl(frame) {
    const binary = atob(frame.data);
    const bytes = new Uint8Array(binary.length);
    for (let idx = 0; idx < binary.length; idx += 1) {
      bytes[idx] = binary.charCodeAt(idx);
    }
    return URL.createObjectURL(new Blob([bytes], { type: frame.media_type }));
  }

  function trimCache(cache, episodeId, cameraKeys, starts, numFrames) {
    const keep = new Set();
    cameraKeys.forEach((cameraKey) => {
      starts.forEach((start) => {
        const end = Math.min(numFrames, start + BATCH_SIZE);
        for (let index = start; index < end; index += 1) {
          keep.add(frameKey(episodeId, cameraKey, index));
        }
      });
    });
    cache.forEach((url, key) => {
      if (!keep.has(key)) {
        URL.revokeObjectURL(url);
        cache.delete(key);
      }
    });
  }

  function clearCache(cache) {
    cache.forEach((url) => URL.revokeObjectURL(url));
    cache.clear();
  }

  window.UniVisFrameCache = { useFrameCache };
})();
