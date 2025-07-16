import { deepStrictEqual, rejects, strictEqual } from 'assert'
import { describe, it } from 'mocha'
import { Readable } from 'readable-stream'
import decode from '../decode.js'

describe('decode', () => {
  it('should be a function', () => {
    strictEqual(typeof decode, 'function')
  })

  it('should return the chunks of a Readable stream concatenated into a Uint8Array', async () => {
    const chunks = [new Uint8Array([97, 98]), new Uint8Array([99, 100])]
    const expected = 'abcd'
    const stream = Readable.from(chunks, { objectMode: false })

    const result = await decode(stream, 'utf8')

    strictEqual(result, expected)
  })

  it('should return an empty Uint8Array if the Readable stream ends without emitting a chunk', async () => {
    const chunks = []
    const expected = ''
    const stream = Readable.from(chunks)

    const result = await decode(stream, 'utf8')

    deepStrictEqual(result, expected)
  })

  it('should forward error from the Readable stream', async () => {
    await rejects(async () => {
      const stream = new Readable({
        read () {
          this.destroy(new Error('test'))
        }
      })

      await decode(stream)
    }, {
      message: 'test'
    })
  })
})
