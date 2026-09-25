function compareVersions(a, b) {
  const pa = a.split('.').map(Number);
  const pb = b.split('.').map(Number);
  const len = Math.max(pa.length, pb.length);
  for (let i = 0; i < len; i++) {
    const na = pa[i] || 0;
    const nb = pb[i] || 0;
    if (na !== nb) return na - nb;
  }
  return 0;
}

function pickVersionForBlender(versions, blenderVersion) {
  if (!versions || versions.length === 0) return null;

  const inRange = versions.filter((v) => {
    const aboveMin = compareVersions(blenderVersion, v.blender_min) >= 0;
    const belowMax = v.blender_max === null || v.blender_max === undefined
      || compareVersions(blenderVersion, v.blender_max) <= 0;
    return aboveMin && belowMax;
  });

  if (inRange.length > 0) {
    inRange.sort((a, b) => compareVersions(b.blender_min, a.blender_min));
    return { version: inRange[0], exact: true };
  }

  const byDistance = [...versions].sort((a, b) => {
    const da = Math.abs(compareVersions(blenderVersion, a.blender_min));
    const db = Math.abs(compareVersions(blenderVersion, b.blender_min));
    return da - db;
  });
  return { version: byDistance[0], exact: false };
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { compareVersions, pickVersionForBlender };
}
