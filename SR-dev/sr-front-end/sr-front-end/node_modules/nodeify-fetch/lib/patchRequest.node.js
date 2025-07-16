import { Readable, Stream } from 'node:stream'

function patch (options = {}) {
  if (options.body) {
    if (options.body.readable && !(options.body instanceof Stream)) {
      options.body = Readable.from(options.body)
    }
  }

  return options
}

export default patch
