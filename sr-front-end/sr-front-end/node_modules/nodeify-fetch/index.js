import fetch, { Headers } from 'node-fetch'
import patchRequest from './lib/patchRequest.node.js'

function nodeifyFetch (url, options) {
  options = patchRequest(options)

  return fetch(url, options)
}

export {
  nodeifyFetch as default,
  Headers
}
