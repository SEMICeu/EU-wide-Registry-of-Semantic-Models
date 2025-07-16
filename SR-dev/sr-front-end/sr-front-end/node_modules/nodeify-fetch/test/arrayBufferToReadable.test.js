import { deepStrictEqual, rejects, strictEqual } from 'assert'
import { describe, it } from 'mocha'
import concat from 'stream-chunks/concat.js'
import arrayBufferToReadable from '../lib/arrayBufferToReadable.js'

describe('arrayBufferToReadable', () => {
  it('should be a function', () => {
    strictEqual(typeof arrayBufferToReadable, 'function')
  })

  it('should forward the given ArrayBuffer as Buffer object', async () => {
    const arrayBuffer = Uint8Array.from([0, 1, 2, 3]).buffer

    const stream = arrayBufferToReadable(async () => arrayBuffer)
    const result = await concat(stream)

    deepStrictEqual(result, Uint8Array.from([0, 1, 2, 3]))
  })

  it('should forward errors', async () => {
    const stream = arrayBufferToReadable(async () => {
      throw new Error('test')
    })

    await rejects(async () => {
      await concat(stream)
    }, {
      message: 'test'
    })
  })
})
