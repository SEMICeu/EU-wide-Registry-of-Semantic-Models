import { rejects, strictEqual } from 'node:assert'
import { isDuplexStream } from 'is-stream'
import { describe, it } from 'mocha'
import rdf from 'rdf-ext'
import { datasetEqual } from 'rdf-test/assert.js'
import Readable from 'readable-stream'
import TripleToQuadTransform from '../index.js'
import * as ns from './support/namespaces.js'

describe('rdf-source-triple-to-quad', () => {
  it('should implement a duplex stream interface', () => {
    const stream = new TripleToQuadTransform(ns.ex.graph)

    strictEqual(isDuplexStream(stream), true)
  })

  it('should forward errors', async () => {
    const errorStream = new Readable({
      read: () => errorStream.destroy(new Error('test'))
    })
    const stream = new TripleToQuadTransform(ns.ex.graph)
    errorStream.pipe(stream)

    await rejects(async () => {
      await rdf.dataset().import(stream)
    })
  })

  it('should patch graph of the quads', async () => {
    const input = rdf.dataset([rdf.quad(ns.ex.subject, ns.ex.predicate, ns.ex.object, ns.ex.graph)])
    const expected = rdf.dataset([rdf.quad(ns.ex.subject, ns.ex.predicate, ns.ex.object, ns.ex.graphPatched)])
    const stream = new TripleToQuadTransform(ns.ex.graphPatched)
    input.toStream().pipe(stream)

    const result = await rdf.dataset().import(stream)

    datasetEqual(result, expected)
  })
})
