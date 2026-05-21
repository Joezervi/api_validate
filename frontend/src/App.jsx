import { useState, useRef } from 'react'
import axios from 'axios'
import { useDropzone } from 'react-dropzone'

function App() {
  const [existing, setExisting] = useState([])
  const [missing, setMissing] = useState([])
  const [loading, setLoading] = useState(false)
  const [excelFile, setExcelFile] = useState(null)
  const pollingRef = useRef(null)

  const onDrop = async (acceptedFiles) => {
    const file = acceptedFiles[0]
    if (!file) return

    const formData = new FormData()
    formData.append('file', file)
    formData.append('customer_name', 'zervi')

    try {
      setLoading(true)
      setExisting([])
      setMissing([])
      setExcelFile(null)

      // Step 1: Upload PDF and get task_id
      const uploadRes = await axios.post('/upload-po', formData)
      const { task_id } = uploadRes.data

      // Step 2: Poll for task completion
      pollingRef.current = setInterval(async () => {
        try {
          const taskRes = await axios.get(`/task/${task_id}`)
          if (taskRes.data.status === 'SUCCESS' && taskRes.data.result) {
            const result = taskRes.data.result
            setExcelFile(result.excel_file)
            setExisting(result.existing || [])
            setMissing(result.missing || [])
            setLoading(false)
            clearInterval(pollingRef.current)
          } else if (taskRes.data.status === 'FAILURE') {
            setLoading(false)
            clearInterval(pollingRef.current)
            alert('Processing failed')
          }
        } catch (err) {
          setLoading(false)
          clearInterval(pollingRef.current)
          alert('Polling failed')
        }
      }, 2000)
    } catch (error) {
      console.error(error)
      alert('Upload failed')
      setLoading(false)
    }
  }

  const { getRootProps, getInputProps } = useDropzone({
    accept: { 'application/pdf': ['.pdf'] },
    onDrop,
  })

  const downloadExcel = () => {
    if (excelFile) {
      window.open(`/download/${excelFile}`)
    }
  }

  return (
    <div style={{ padding: 40 }}>
      <h1>Customer PO Checker</h1>

      <div
        {...getRootProps()}
        style={{
          border: '2px dashed #ccc',
          padding: 40,
          textAlign: 'center',
          cursor: 'pointer',
          marginBottom: 20,
        }}
      >
        <input {...getInputProps()} />
        <p>Drag &amp; drop a PO PDF here, or click to select</p>
      </div>

      {loading && <p>Processing PDF...</p>}

      {excelFile && (
        <button onClick={downloadExcel}>Download Excel Report</button>
      )}

      <hr />

      <h2>Existing SKUs ({existing.length})</h2>
      <table border="1" cellPadding="10">
        <thead>
          <tr>
            <th>SKU</th>
            <th>Product Name</th>
            <th>Category</th>
            <th>Price</th>
          </tr>
        </thead>
        <tbody>
          {existing.map((item, index) => (
            <tr key={index}>
              <td>{item.sku}</td>
              <td>{item.product_name}</td>
              <td>{item.category}</td>
              <td>{item.price}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <hr />

      <h2>Missing SKUs ({missing.length})</h2>
      <table border="1" cellPadding="10">
        <thead>
          <tr>
            <th>SKU</th>
            <th>Product Name</th>
            <th>Category</th>
            <th>Price</th>
          </tr>
        </thead>
        <tbody>
          {missing.map((item, index) => (
            <tr key={index}>
              <td>{item.sku}</td>
              <td>{item.product_name}</td>
              <td>{item.category}</td>
              <td>{item.price}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default App
