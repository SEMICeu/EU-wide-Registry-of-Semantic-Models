import { createHash, randomBytes } from 'crypto'
import { dirname, resolve } from 'path'
import express from 'express'
import withPlainServer from 'express-as-promise/withServer.js'

const _dirname = dirname((new URL(import.meta.url)).pathname)

async function withServer (callback) {
  await withPlainServer(async server => {
    server.app.use(express.static(resolve(_dirname, '../../node_modules/test-runner-browser/public')))
    server.app.use(express.static(resolve(_dirname, '../../node_modules/mocha')))
    server.app.use(express.static(resolve(_dirname, '../../dist/')))

    server.app.get('/plain-text', (req, res) => res.send('text'))

    server.app.post('/plain-text', express.text({ type: '*/*' }), (req, res) => {
      if (req.body === 'test') {
        res.status(201)
      } else {
        res.status(500)
      }

      res.end()
    })

    server.app.get('/random', (req, res) => {
      const content = randomBytes(1 << 20)
      const hash = createHash('sha256')

      hash.update(content)

      res.set('sha256', hash.digest('hex')).send(content)
    })

    await callback(server)
  })
}

export default withServer
