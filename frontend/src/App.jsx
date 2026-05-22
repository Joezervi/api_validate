import { useState } from 'react'
import axios from 'axios'
import { useDropzone } from 'react-dropzone'

function App() {
  const [existing, setExisting] = useState([])
  const [missing, setMissing] = useState([])
  const [loading, setLoading] = useState(false)
  const [excelFile, setExcelFile] = useState(null)

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

      const res = await axios.post('/upload-po', formData)
      const result = res.data

      setExcelFile(result.excel_file)
      setExisting(result.existing || [])
      setMissing(result.missing || [])
    } catch (error) {
      console.error(error)
      alert('Processing failed')
    } finally {
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
