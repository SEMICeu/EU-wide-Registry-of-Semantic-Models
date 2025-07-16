import chunks from './chunks.js'
import concatChunks from './concatChunks.js'

async function concat (stream) {
  return concatChunks(await chunks(stream))
}

export default concat
