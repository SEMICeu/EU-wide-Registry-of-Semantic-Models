import { deepStrictEqual, rejects, strictEqual } from 'assert'
import { describe, it } from 'mocha'
import { Readable } from 'readable-stream'
import concat from '../concat.js'

describe('concat', () => {
  it('should be a function', () => {
    strictEqual(typeof concat, 'function')
  })

  it('should return the chunks of a Readable stream concatenated into a Uint8Array', async () => {
    const chunks = [new Uint8Array([0, 1]), new Uint8Array([2, 3])]
    const expected = new Uint8Array([0, 1, 2, 3])
    const stream = Readable.from(chunks)

    const result = await concat(stream)

    deepStrictEqual(result, expected)
  })

  it('should return an empty Uint8Array if the Readable stream ends without emitting a chunk', async () => {
    const chunks = []
    const expected = new Uint8Array([])
    const stream = Readable.from(chunks)

    const result = await concat(stream)

    deepStrictEqual(result, expected)
  })

  it('should forward error from the Readable stream', async () => {
    await rejects(async () => {
      const stream = new Readable({
        read () {
          this.destroy(new Error('test'))
        }
      })

      await concat(stream)
    }, {
      message: 'test'
    })
  })
})
