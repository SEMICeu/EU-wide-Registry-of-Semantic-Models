import { deepStrictEqual, rejects, strictEqual } from 'assert'
import { describe, it } from 'mocha'
import { Readable } from 'readable-stream'
import chunks from '../chunks.js'

describe('chunks', () => {
  it('should be a function', () => {
    strictEqual(typeof chunks, 'function')
  })

  describe('suite 123', () => {
    it('should return the chunks of a Readable stream in an array', async () => {
      const input = ['ab', 'cd']
      const stream = Readable.from(input)

      const result = await chunks(stream)

      deepStrictEqual(result, input)
    })
  })

  it('should return an empty array if the Readable stream ends without emitting a chunk', async () => {
    const input = []
    const stream = Readable.from(input)

    const result = await chunks(stream)

    deepStrictEqual(result, input)
  })

  it('should forward error from the Readable stream', async () => {
    await rejects(async () => {
      const stream = new Readable({
        read () {
          this.destroy(new Error('test'))
        }
      })

      await chunks(stream)
    }, {
      message: 'test'
    })
  })
})
