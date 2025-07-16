import assert from 'assert'
import { isStream, isReadableStream, isWritableStream } from 'is-stream'
import { describe, it } from 'mocha'
import { PassThrough } from 'readable-stream'
import decode from 'stream-chunks/decode.js'
import duplexToWritable from '../writable.js'

describe('writable', () => {
  it('should be a function', () => {
    assert.strictEqual(typeof duplexToWritable, 'function')
  })

  it('should return a stream', () => {
    const result = duplexToWritable(new PassThrough())

    assert(isStream(result))
  })

  it('should wrap only the writable interface', () => {
    const result = duplexToWritable(new PassThrough())

    assert(!isReadableStream(result))
    assert(!result.readable) // used by stream.finished
    assert(isWritableStream(result))
    assert(result.writable) // used by stream.finished
  })

  it('should keep object mode information', () => {
    const result = duplexToWritable(new PassThrough({ objectMode: true }))

    assert(result._writableState.objectMode)
  })

  it('should forward the content', async () => {
    const output = new PassThrough()
    const input = duplexToWritable(output)

    input.write('a')
    input.write('b')
    input.end('c')

    const result = await decode(output)

    assert.strictEqual(result, 'abc')
  })
})
