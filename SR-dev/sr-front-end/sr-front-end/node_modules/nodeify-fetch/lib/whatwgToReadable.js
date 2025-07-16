import { Readable } from 'readable-stream'

function whatwgToReadable (whatwg) {
  return new Readable({
    read: async function () {
      try {
        let chunk, full

        do {
          chunk = await whatwg.read()

          if (chunk.done) {
            this.push(null)
          } else {
            full = !this.push(chunk.value)
          }
        } while (!chunk.done && !full)
      } catch (err) {
        this.destroy(err)
      }
    }
  })
}

export default whatwgToReadable
