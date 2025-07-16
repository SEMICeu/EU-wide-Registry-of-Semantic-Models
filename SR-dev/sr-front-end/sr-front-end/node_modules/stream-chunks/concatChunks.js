function concatChunks (chunks) {
  const length = chunks.reduce((length, chunk) => length + chunk.length, 0)
  const merged = new Uint8Array(length)

  let offset = 0

  for (const chunk of chunks) {
    merged.set(chunk, offset)
    offset += chunk.length
  }

  return merged
}

export default concatChunks
