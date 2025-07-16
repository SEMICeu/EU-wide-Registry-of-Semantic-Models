import once from 'lodash/once.js'
import { Readable } from 'readable-stream'

function arrayBufferToReadable (callback) {
  return new Readable({
    read: once(async function () {
      try {
        this.push(new Uint8Array(await callback()))
        this.push(null)
      } catch (err) {
        this.destroy(err)
      }
    })
  })
}

export default arrayBufferToReadable
