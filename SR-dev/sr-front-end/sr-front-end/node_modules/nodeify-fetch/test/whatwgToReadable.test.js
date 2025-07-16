import { deepStrictEqual, rejects, strictEqual } from 'assert'
import { describe, it } from 'mocha'
import delay from 'promise-the-world/delay.js'
import chunks from 'stream-chunks/chunks.js'
import concat from 'stream-chunks/concat.js'
import whatwgToReadable from '../lib/whatwgToReadable.js'
import encodeString from './support/encodeString.js'
import { toErrorStream, toStream } from './support/toWhatwg.js'

describe('whatwgToReadable', () => {
  it('should be a function', () => {
    strictEqual(typeof whatwgToReadable, 'function')
  })

  it('should handle string chunks from the WHATWG readable', async () => {
    const input = ['ab', 'cd']
    const expected = encodeString(input.join(''))
    const stream = whatwgToReadable(toStream(input))

    const result = await concat(stream)

    deepStrictEqual(result, expected)
  })

  it('should handle Uint8Array chunks from the WHATWG readable', async () => {
    const input = [new Uint8Array([0, 1]), new Uint8Array([2, 3])]
    const expected = new Uint8Array([0, 1, 2, 3])
    const stream = whatwgToReadable(toStream(input))

    const result = await concat(stream)

    deepStrictEqual(result, expected)
  })

  it('should forward errors from the WHATWG readable', async () => {
    const stream = whatwgToReadable(toErrorStream(new Error('test')))

    await rejects(async () => {
      await chunks(stream)
    }, {
      message: 'test'
    })
  })

  it('should respect the highwater mark', async () => {
    const source = toStream(['ab', 'cd'])
    const stream = whatwgToReadable(source)
    stream._readableState.highWaterMark = 1

    stream.read()

    await delay(1)

    strictEqual(source.values.length, 1)
  })
})
