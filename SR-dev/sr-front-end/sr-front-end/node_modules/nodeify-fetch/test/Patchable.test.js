import { deepStrictEqual, notStrictEqual, strictEqual } from 'assert'
import { describe, it } from 'mocha'
import Patchable from '../lib/Patchable.js'

describe('Patchable', () => {
  it('should be a constructor', () => {
    strictEqual(typeof Patchable, 'function')
  })

  it('should wrap the object method', () => {
    let touched = false

    class Test {
      test () {
        touched = true
      }
    }

    const obj = new Test()
    const patchable = new Patchable(obj, {})

    patchable.test()

    notStrictEqual(patchable.test, obj.test)
    strictEqual(touched, true)
  })

  it('should wrap the getter of the object', () => {
    const value = 'test'

    class Test {
      get test () {
        return value
      }
    }

    const obj = new Test()
    const patchable = new Patchable(obj, {})

    strictEqual(patchable.test, 'test')
  })

  it('should wrap the setters of the object', () => {
    let value = 'initial'

    class Test {
      get test () {
        return value
      }

      set test (v) {
        value = v
      }
    }

    const obj = new Test()
    const patchable = new Patchable(obj, {})
    patchable.test = 'changed'

    strictEqual(patchable.test, 'changed')
  })

  it('should replace the given property', () => {
    class Test {
      get property () {
        return 'test'
      }
    }

    const obj = new Test()
    const patchable = new Patchable(obj, { property: 'patched' })

    strictEqual(patchable.property, 'patched')
  })

  it('should replace the given method', () => {
    class Test {
      method () {
        return 'test'
      }
    }

    const method = () => {
      return 'patched'
    }

    const obj = new Test()
    const patchable = new Patchable(obj, { method })

    strictEqual(patchable.method(), 'patched')
  })

  describe('.properties', () => {
    it('should list all properties of the class', () => {
      class Test {
        test0 () {}
        test1 () {}
      }

      const properties = Patchable.properties(new Test())

      deepStrictEqual(properties, ['constructor', 'test0', 'test1'])
    })
  })
})
