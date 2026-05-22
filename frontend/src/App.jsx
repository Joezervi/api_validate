import { useState } from 'react'
import axios from 'axios'
import { useDropzone } from 'react-dropzone'

function App() {
  const [existing, setExisting] = useState([])
  const [missing, setMissing] = useState([])
  const [loading, setLoading] = useState(false)
  const [excelFile, setExcelFile] = useState(null)
  const [markdownReport, setMarkdownReport] = useState(null)
  const [copied, setCopied] = useState(false)

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
      setMarkdownReport(null)
      setCopied(false)

      const res = await axios.post('/upload-po', formData)
      const result = res.data

      setExcelFile(result.excel_file)
      setMarkdownReport(result.markdown_report || null)
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

  const copyMarkdown = async () => {
    if (markdownReport) {
      await navigator.clipboard.writeText(markdownReport)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  const notedStyle = (noted) => {
    if (!noted) return {}
    if (noted.includes('SKU not exist')) return { color: '#dc2626', fontWeight: 600 }
    if (noted.includes('Case mismatch')) return { color: '#d97706' }
    if (noted.includes('Extra space')) return { color: '#d97706' }
    if (noted.includes('Special character')) return { color: '#7c3aed' }
    if (noted.includes('Character difference')) return { color: '#7c3aed' }
    if (noted.includes('Partial match')) return { color: '#0891b2' }
    return { color: '#6b7280' }
  }

  return (
    <div style={{ padding: 40, fontFamily: 'system-ui, sans-serif', maxWidth: 1400, margin: '0 auto' }}>
      <h1 style={{ fontSize: 24, marginBottom: 8 }}>Customer PO Checker</h1>
      <p style={{ color: '#6b7280', marginBottom: 24, fontSize: 14 }}>
        Data Verification Specialist — 6‑step SKU verification
      </p>

      <div
        {...getRootProps()}
        style={{
          border: '2px dashed #d1d5db',
          borderRadius: 8,
          padding: 40,
          textAlign: 'center',
          cursor: 'pointer',
          marginBottom: 24,
          backgroundColor: '#f9fafb',
          transition: 'border-color 0.2s',
        }}
      >
        <input {...getInputProps()} />
        <p style={{ margin: 0, color: '#374151', fontSize: 15 }}>
          Drag &amp; drop a PO PDF here, or click to select
        </p>
      </div>

      {loading && (
        <div style={{ padding: 20, textAlign: 'center' }}>
          <p style={{ color: '#6b7280' }}>Processing PDF — running 6‑step verification...</p>
        </div>
      )}

      {excelFile && (
        <div style={{ marginBottom: 24, display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          <button
            onClick={downloadExcel}
            style={{
              padding: '10px 20px',
              backgroundColor: '#2563eb',
              color: '#fff',
              border: 'none',
              borderRadius: 6,
              cursor: 'pointer',
              fontSize: 14,
              fontWeight: 500,
            }}
          >
            Download Excel Report
          </button>
          {markdownReport && (
            <button
              onClick={copyMarkdown}
              style={{
                padding: '10px 20px',
                backgroundColor: copied ? '#059669' : '#374151',
                color: '#fff',
                border: 'none',
                borderRadius: 6,
                cursor: 'pointer',
                fontSize: 14,
                fontWeight: 500,
              }}
            >
              {copied ? 'Copied!' : 'Copy Markdown Table'}
            </button>
          )}
        </div>
      )}

      {/* ── Markdown Report Preview ── */}
      {markdownReport && (
        <div style={{ marginBottom: 32 }}>
          <h2 style={{ fontSize: 18, marginBottom: 12 }}>Verification Report (Markdown)</h2>
          <pre
            style={{
              backgroundColor: '#f3f4f6',
              padding: 16,
              borderRadius: 8,
              overflowX: 'auto',
              fontSize: 13,
              lineHeight: 1.6,
              border: '1px solid #e5e7eb',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-all',
            }}
          >
            {markdownReport}
          </pre>
        </div>
      )}

      {/* ── Existing SKUs ── */}
      {existing.length > 0 && (
        <>
          <h2 style={{ fontSize: 18, marginBottom: 12, color: '#059669' }}>
            Existing SKUs ({existing.length})
          </h2>
          <div style={{ overflowX: 'auto', marginBottom: 32 }}>
            <table
              style={{
                width: '100%',
                borderCollapse: 'collapse',
                fontSize: 14,
              }}
            >
              <thead>
                <tr style={{ backgroundColor: '#f3f4f6' }}>
                  <th style={thStyle}>SKU</th>
                  <th style={thStyle}>Barcode</th>
                  <th style={thStyle}>Product Name</th>
                  <th style={thStyle}>Category</th>
                  <th style={thStyle}>Price</th>
                </tr>
              </thead>
              <tbody>
                {existing.map((item, index) => (
                  <tr key={index} style={{ borderBottom: '1px solid #e5e7eb' }}>
                    <td style={tdStyle}>{item.sku}</td>
                    <td style={tdStyle}>{item.barcode || '—'}</td>
                    <td style={tdStyle}>{item.product_name || '—'}</td>
                    <td style={tdStyle}>{item.category || '—'}</td>
                    <td style={tdStyle}>{item.price || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* ── Missing SKUs — 5‑column format ── */}
      {missing.length > 0 && (
        <>
          <h2 style={{ fontSize: 18, marginBottom: 12, color: '#dc2626' }}>
            Missing SKUs ({missing.length})
          </h2>
          <div style={{ overflowX: 'auto', marginBottom: 32 }}>
            <table
              style={{
                width: '100%',
                borderCollapse: 'collapse',
                fontSize: 14,
              }}
            >
              <thead>
                <tr style={{ backgroundColor: '#fef2f2' }}>
                  <th style={thStyle}>SKU Missing</th>
                  <th style={thStyle}>Barcode</th>
                  <th style={thStyle}>Product Name</th>
                  <th style={thStyle}>Category Name</th>
                  <th style={{ ...thStyle, minWidth: 280 }}>Noted</th>
                </tr>
              </thead>
              <tbody>
                {missing.map((item, index) => (
                  <tr
                    key={index}
                    style={{
                      borderBottom: '1px solid #e5e7eb',
                      backgroundColor: index % 2 === 0 ? '#fff' : '#fef2f2',
                    }}
                  >
                    <td style={{ ...tdStyle, fontFamily: 'monospace' }}>
                      {item.sku_missing}
                    </td>
                    <td style={tdStyle}>{item.barcode}</td>
                    <td style={tdStyle}>{item.product_name}</td>
                    <td style={tdStyle}>{item.category_name}</td>
                    <td style={{ ...tdStyle, ...notedStyle(item.noted) }}>
                      {item.noted}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {!loading && existing.length === 0 && missing.length === 0 && (
        <p style={{ color: '#9ca3af', textAlign: 'center', marginTop: 32 }}>
          Upload a PO PDF to begin verification.
        </p>
      )}
    </div>
  )
}

const thStyle = {
  padding: '10px 12px',
  textAlign: 'left',
  fontWeight: 600,
  fontSize: 13,
  color: '#374151',
  borderBottom: '2px solid #d1d5db',
  whiteSpace: 'nowrap',
}

const tdStyle = {
  padding: '10px 12px',
  color: '#1f2937',
  verticalAlign: 'top',
}

export default App
