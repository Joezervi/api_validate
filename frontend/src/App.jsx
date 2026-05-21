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

    formData.append("file", file)

    try {

      setLoading(true)

      const response = await axios.post(
        "http://localhost:8000/check-po",
        formData
      )

      setExisting(response.data.existing)

      setMissing(response.data.missing)

      setExcelFile(response.data.excel_file)

    } catch (error) {

      console.error(error)

      alert("Upload failed")

    } finally {

      setLoading(false)
    }
  }

  const {
    getRootProps,
    getInputProps
  } = useDropzone({
    import { useRef } from 'react'
    accept: {
      'application/pdf': ['.pdf']
    },
    onDrop
  })
      const pollingRef = useRef(null)

  const downloadExcel = () => {

    window.open(
      `http://localhost:8000/download/${excelFile}`
    )
  }

  return (
    <div style={{ padding: 40 }}>

      <h1>Customer PO Checker</h1>

      <div
        {...getRootProps()}
          setLoading(true)
          setExisting([])
          setMissing([])
          setExcelFile(null)
          // Step 1: Upload PDF and get task_id
          const uploadRes = await axios.post(
            "http://localhost:8000/upload-po",
            formData,
            { params: { customer_name: "zervi" } }
          )
          const { task_id } = uploadRes.data
          // Step 2: Poll for task completion
          const pollTask = async () => {
            try {
              const taskRes = await axios.get(
                `http://localhost:8000/task/${task_id}`
              )
              if (taskRes.data.status === "SUCCESS" && taskRes.data.result) {
                setExcelFile(taskRes.data.result.excel_file)
                // Optionally, fetch more details if needed
                setLoading(false)
                clearInterval(pollingRef.current)
              } else if (taskRes.data.status === "FAILURE") {
                setLoading(false)
                clearInterval(pollingRef.current)
                alert("Processing failed")
              }
            } catch (err) {
              setLoading(false)
              clearInterval(pollingRef.current)
              alert("Polling failed")
            }
          }
          pollingRef.current = setInterval(pollTask, 2000)
      </div>

      {loading && <p>Checking PDF...</p>}

      {excelFile && (
        <button onClick={downloadExcel}>
          Download Excel
        </button>
      )}

      <hr />

      <h2>Existing SKU</h2>

      <table border="1" cellPadding="10">

        <thead>
        if (excelFile) {
          window.open(
            `http://localhost:8000/download/${excelFile}`
          )
        }
            <th>Category</th>
            <th>Price</th>
          </tr>
        </thead>

        <tbody>

          {existing.map((item, index) => (
            <tr key={index}>
              <td>{item.SKU}</td>
              <td>{item["Product Name"]}</td>
              <td>{item.Category}</td>
              <td>{item.Price}</td>
            </tr>
          ))}

        </tbody>

      </table>

      <hr />

      <h2>Missing SKU</h2>

      <table border="1" cellPadding="10">

        <thead>
          <tr>
            <th>SKU</th>
            <th>Product</th>
            <th>Category</th>
            <th>Price</th>
          </tr>
        </thead>

        <tbody>

          {missing.map((item, index) => (
            <tr key={index}>
              <td>{item.SKU}</td>
              <td>{item["Product Name"]}</td>
              <td>{item.Category}</td>
              <td>{item.Price}</td>
            </tr>
          ))}

        </tbody>

      </table>

    </div>
  )
}

export default App