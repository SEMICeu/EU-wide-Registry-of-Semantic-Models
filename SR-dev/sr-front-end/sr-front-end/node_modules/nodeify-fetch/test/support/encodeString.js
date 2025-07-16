function encodeString (str) {
  const encoder = new TextEncoder()

  return encoder.encode(str)
}

export default encodeString
