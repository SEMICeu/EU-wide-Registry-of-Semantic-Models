import { deepStrictEqual, strictEqual } from 'assert'
import { describe, it } from 'mocha'
import concatChunks from '../concatChunks.js'

describe('concatChunks', () => {
  it('should be a function', () => {
    strictEqual(typeof concatChunks, 'function')
  })

  it('should return the chunks concatenated into a Uint8Array', () => {
    const chunks = [new Uint8Array([0, 1]), new Uint8Array([2, 3])]
    const expected = new Uint8Array([0, 1, 2, 3])

    const result = concatChunks(chunks)

    deepStrictEqual(result, expected)
  })

  it('should return an empty Uint8Array if the array of chunks is empty', () => {
    const chunks = []
    const expected = new Uint8Array([])

    const result = concatChunks(chunks)

    deepStrictEqual(result, expected)
  })
})
