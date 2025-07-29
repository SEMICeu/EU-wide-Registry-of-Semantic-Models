function toErrorStream (error) {
  return {
    read: async () => {
      throw error
    }
  }
}

function toReader (values) {
  return {
    getReader: () => {
      return toStream(values)
    }
  }
}

function toStream (values) {
  values = Array.isArray(values) ? values : [values]

  return {
    read: async () => {
      if (values.length === 0) {
        return { done: true }
      }

      return {
        value: values.shift(),
        done: false
      }
    },
    values
  }
}

export {
  toErrorStream,
  toReader,
  toStream
}
