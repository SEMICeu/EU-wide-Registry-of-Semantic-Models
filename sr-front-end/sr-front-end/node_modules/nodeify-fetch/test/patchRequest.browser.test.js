import { deepStrictEqual, strictEqual } from 'assert'
import { describe, it } from 'mocha'
import { Readable } from 'readable-stream'
import patchRequest from '../lib/patchRequest.browser.js'
import encodeString from './support/encodeString.js'

describe('patchRequest', () => {
  it('should be a function', () => {
    strictEqual(typeof patchRequest, 'function')
  })

  it('should be able to be called without options', async () => {
    await patchRequest()
  })

  it('should ignore the body if it\'s not a stream', async () => {
    const body = 'test'

    const options = await patchRequest({ body })

    strictEqual(options.body, body)
  })

  it('should convert a string stream to a string', async () => {
    const body = new Readable({
      objectMode: true,
      read: () => {
        body.push('test')
        body.push('1234')
        body.push(null)
      }
    })

    const options = await patchRequest({ body })

    strictEqual(options.body, 'test1234')
  })

  it('should convert a buffer stream to a Uint8Array', async () => {
    const body = new Readable({
      read: () => {
        body.push(encodeString('test'))
        body.push(encodeString('1234'))
        body.push(null)
      }
    })

    const options = await patchRequest({ body })

    strictEqual(options.body.BYTES_PER_ELEMENT, 1)
    deepStrictEqual(options.body, encodeString('test1234'))
  })

  it('should convert an empty stream to an empty string', async () => {
    const body = new Readable({
      read: () => {
        body.push(null)
      }
    })

    const options = await patchRequest({ body })

    strictEqual(options.body, '')
  })
})
