import chunks from 'stream-chunks/chunks.js'
import concatChunks from 'stream-chunks/concatChunks.js'

async function patch (options = {}) {
  if (!options.body || !options.body.readable) {
    return options
  }

  // read the whole input stream...
  const content = await chunks(options.body)

  // ...and if there is any content convert it to a single Uint8Array or string
  if (content.length > 0) {
    if (content[0].BYTES_PER_ELEMENT === 1) {
      options.body = concatChunks(content)
    } else {
      options.body = content.join('')
    }
  } else {
    options.body = ''
  }

  return options
}

export default patch
