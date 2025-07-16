async function chunks (stream) {
  const chunks = []

  for await (const chunk of stream) {
    chunks.push(chunk)
  }

  return chunks
}

export default chunks
