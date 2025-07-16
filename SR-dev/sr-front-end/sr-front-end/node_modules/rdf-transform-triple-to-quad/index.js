import rdf from '@rdfjs/data-model'
import { Transform } from 'readable-stream'

class TripleToQuadTransform extends Transform {
  constructor (graph, { factory = rdf } = {}) {
    super({ objectMode: true })

    this.factory = factory
    this.graph = graph || this.factory.defaultGraph()

    this.on('pipe', input => {
      input.on('error', err => {
        this.emit('error', err)
      })
    })
  }

  _transform (triple, encoding, callback) {
    const quad = this.factory.quad(triple.subject, triple.predicate, triple.object, this.graph)

    callback(null, quad)
  }
}

export default TripleToQuadTransform
