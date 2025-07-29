import { strictEqual } from 'assert'
import { describe, it } from 'mocha'
import chunks from '../chunks.js'
import concat from '../concat.js'
import concatChunks from '../concatChunks.js'
import decode from '../decode.js'
import * as streamChunks from '../index.js'

describe('stream-chunks', () => {
  it('should export the chunks function', () => {
    strictEqual(streamChunks.chunks, chunks)
  })

  it('should export the concat function', () => {
    strictEqual(streamChunks.concat, concat)
  })

  it('should export the concatChunks function', () => {
    strictEqual(streamChunks.concatChunks, concatChunks)
  })

  it('should export the decode function', () => {
    strictEqual(streamChunks.decode, decode)
  })
})
