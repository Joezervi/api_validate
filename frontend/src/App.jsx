import { useState } from 'react'
import axios from 'axios'
import { useDropzone } from 'react-dropzone'

// ── API URL — auto-detects Docker dev vs Vercel prod ──────────────────

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

const apiUrl = (path) => {
  if (path.startsWith('http')) return path
  return `${API_BASE}${path}`
}

const COLUMNS = [
  { key: 'sku',          label: 'SKU',           width: 140 },
  { key: 'barcode',      label: 'Barcode',       width: 140 },
  { key: 'supplier_code',label: 'Supplier Code',  width: 120 },
  { key: 'product_name', label: 'Product Name',   width: 200 },
  { key: 'job_no',       label: 'Job No.',        width: 110 },
  { key: 'qty',          label: 'Qty',            width: 70  },
  { key: 'unit_price',   label: 'Unit Price',     width: 100 },
  { key: 'subtotal',     label: 'Subtotal',       width: 100 },
]

// ── Styles ─────────────────────────────────────────────────────────────

const thStyle = {
  padding: '8px 10px', textAlign: 'left', fontWeight: 600,
  fontSize: 12, color: '#374151', borderBottom: '2px solid #d1d5db',
  whiteSpace: 'nowrap', backgroundColor: '#f9fafb',
}

const tdStyle = { padding: '6px 8px', color: '#1f2937', verticalAlign: 'top' }

const inputStyle = {
  width: '100%', border: '1px solid #d1d5db', borderRadius: 4,
  padding: '5px 7px', fontSize: 13, fontFamily: 'monospace',
  boxSizing: 'border-box',
}

const btnStyle = {
  padding: '9px 18px', border: 'none', borderRadius: 6,
  cursor: 'pointer', fontSize: 14, fontWeight: 500, color: '#fff',
}

// ── Component ──────────────────────────────────────────────────────────

function App() {
  // ── Extract state
  const [extracted, setExtracted] = useState([])       // raw parsed rows
  const [extracting, setExtracting] = useState(false)

  // ── Verify state
  const [existing, setExisting] = useState([])
  const [missing, setMissing] = useState([])
  const [verifying, setVerifying] = useState(false)
  const [excelFile, setExcelFile] = useState(null)
  const [markdownReport, setMarkdownReport] = useState(null)
  const [copied, setCopied] = useState(false)
  const [clearing, setClearing] = useState(false)

  // ── Step 1: Upload → Extract ──────────────────────────────────────

  const onDrop = async (acceptedFiles) => {
    const file = acceptedFiles[0]
    if (!file) return

    const ext = file.name.split('.').pop()?.toLowerCase() || ''
    const isSpreadsheet = ['csv', 'xlsx', 'xls', 'xlsm', 'tsv'].includes(ext)
    const endpoint = isSpreadsheet ? '/extract-file' : '/extract-po'

    const formData = new FormData()
    formData.append('file', file)
    if (!isSpreadsheet) {
      formData.append('customer_name', 'zervi')
    }

    try {
      setExtracting(true)
      setExtracted([])
      setExisting([]); setMissing([]); setExcelFile(null); setMarkdownReport(null)

      const res = await axios.post(apiUrl(endpoint), formData)
      setExtracted(res.data.products || [])
    } catch (err) {
      console.error(err)
      alert(`Failed to extract data from ${isSpreadsheet ? 'spreadsheet' : 'PDF'}`)
    } finally {
      setExtracting(false)
    }
  }

  const { getRootProps, getInputProps } = useDropzone({
    accept: {
      'application/pdf': ['.pdf'],
      'text/csv': ['.csv', '.tsv'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'application/vnd.ms-excel': ['.xls', '.xlsm'],
    },
    onDrop,
    disabled: extracting || verifying,
  })

  // ── Editable table helpers ─────────────────────────────────────────

  const updateCell = (rowIdx, colKey, value) => {
    setExtracted(prev => {
      const next = [...prev]
      next[rowIdx] = { ...next[rowIdx], [colKey]: value }
      return next
    })
  }

  const addRow = () => {
    const empty = {}
    COLUMNS.forEach(c => { empty[c.key] = '' })
    setExtracted(prev => [...prev, empty])
  }

  const deleteRow = (rowIdx) => {
    setExtracted(prev => prev.filter((_, i) => i !== rowIdx))
  }

  // ── Step 2: Verify ────────────────────────────────────────────────

  const runVerify = async () => {
    // Filter out rows without SKU
    const products = extracted.filter(r => r.sku && r.sku.trim())
    if (!products.length) {
      alert('No rows with a SKU to verify.')
      return
    }

    const body = {
      customer_name: 'zervi',
      po_number: null,
      products: products.map(p => ({
        sku: p.sku,
        product_name: p.product_name || '',
        barcode: p.barcode || '',
        supplier_code: p.supplier_code || '',
        job_no: p.job_no || '',
        qty: p.qty ? parseInt(p.qty) : null,
        unit_price: p.unit_price ? parseFloat(p.unit_price) : null,
        subtotal: p.subtotal ? parseFloat(p.subtotal) : null,
      })),
    }

    try {
      setVerifying(true)
      setExisting([]); setMissing([]); setExcelFile(null); setMarkdownReport(null)

      const res = await axios.post(apiUrl('/verify-po'), body)
      const result = res.data

      setExcelFile(result.excel_file)
      setMarkdownReport(result.markdown_report || null)
      setExisting(result.existing || [])
      setMissing(result.missing || [])
    } catch (err) {
      console.error(err)
      alert('Verification failed')
    } finally {
      setVerifying(false)
    }
  }

  const downloadExcel = () => {
    if (excelFile) window.open(apiUrl(`/download/${excelFile}`))
  }

  const copyMarkdown = async () => {
    if (markdownReport) {
      await navigator.clipboard.writeText(markdownReport)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  const clearOutputs = async () => {
    try {
      setClearing(true)
      await axios.post(apiUrl('/cleanup'), { all_outputs: true })
      setExisting([])
      setMissing([])
      setExcelFile(null)
      setMarkdownReport(null)
    } catch (err) {
      console.error(err)
      alert('Failed to clear output files')
    } finally {
      setClearing(false)
    }
  }

  const notedColor = (noted) => {
    if (!noted) return {}
    if (noted.includes('SKU not exist')) return { color: '#dc2626', fontWeight: 600 }
    if (noted.includes('Case mismatch')) return { color: '#d97706' }
    if (noted.includes('Extra space')) return { color: '#d97706' }
    if (noted.includes('Special character')) return { color: '#7c3aed' }
    if (noted.includes('Character difference')) return { color: '#7c3aed' }
    if (noted.includes('Partial match')) return { color: '#0891b2' }
    return { color: '#6b7280' }
  }

  const hasResults = existing.length > 0 || missing.length > 0

  // ── Render ─────────────────────────────────────────────────────────

  return (
    <div style={{ padding: 32, fontFamily: 'system-ui, sans-serif', maxWidth: 1500, margin: '0 auto' }}>
      <h1 style={{ fontSize: 22, marginBottom: 4 }}>Customer PO Checker</h1>
      <p style={{ color: '#6b7280', marginBottom: 20, fontSize: 13 }}>
        Drop a PO file (PDF, CSV, or Excel) → review &amp; edit → verify
      </p>

      {/* ── Upload ──────────────────────────────────────────────── */}
      <div
        {...getRootProps()}
        style={{
          border: '2px dashed #d1d5db', borderRadius: 8, padding: 28,
          textAlign: 'center', cursor: extracting ? 'wait' : 'pointer',
          marginBottom: 20, backgroundColor: '#fafafa',
          opacity: extracting ? 0.6 : 1,
        }}
      >
        <input {...getInputProps()} />
        <p style={{ margin: 0, color: '#374151', fontSize: 14 }}>
          {extracting ? 'Extracting data...' : 'Drop a PO file (PDF, CSV, Excel) here, or click to select'}
        </p>
      </div>

      {/* ── Editable table — always visible ──────────────────────── */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12, flexWrap: 'wrap' }}>
          <h2 style={{ fontSize: 16, margin: 0 }}>
            Extracted Data ({extracted.length} rows)
          </h2>
          <button onClick={addRow} style={{ ...btnStyle, backgroundColor: '#6b7280', fontSize: 12, padding: '6px 14px' }}>
            + Add Row
          </button>
          {extracted.length === 0 && (
            <button onClick={() => { addRow(); addRow(); addRow(); addRow(); addRow() }}
              style={{ ...btnStyle, backgroundColor: '#0891b2', fontSize: 12, padding: '6px 14px' }}>
              Start Manual Entry
            </button>
          )}
          {extracted.length > 0 && (
            <button onClick={() => { setExtracted([]); setExisting([]); setMissing([]); setExcelFile(null); setMarkdownReport(null) }}
              style={{ ...btnStyle, backgroundColor: '#dc2626', fontSize: 12, padding: '6px 14px' }}>
              Clear Form
            </button>
          )}
          <div style={{ flex: 1 }} />
          <button
            onClick={runVerify}
            disabled={verifying}
            style={{
              ...btnStyle, backgroundColor: verifying ? '#9ca3af' : '#2563eb',
              padding: '10px 28px', fontSize: 15,
            }}
          >
            {verifying ? 'Verifying...' : 'Verify'}
          </button>
        </div>

        <div style={{ overflowX: 'auto', border: '1px solid #e5e7eb', borderRadius: 8 }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr>
                {COLUMNS.map(c => (
                  <th key={c.key} style={{ ...thStyle, minWidth: c.width }}>{c.label}</th>
                ))}
                <th style={{ ...thStyle, width: 50 }}></th>
              </tr>
            </thead>
            <tbody>
              {extracted.length === 0 ? (
                <tr>
                  <td colSpan={COLUMNS.length + 1} style={{ ...tdStyle, textAlign: 'center', color: '#9ca3af', padding: '32px 8px' }}>
                    Upload a file or click <b>Start Manual Entry</b> to begin
                  </td>
                </tr>
              ) : (
                extracted.map((row, ri) => (
                  <tr key={ri} style={{ borderBottom: '1px solid #e5e7eb' }}>
                    {COLUMNS.map(c => (
                      <td key={c.key} style={tdStyle}>
                        <input
                          style={inputStyle}
                          value={row[c.key] ?? ''}
                          onChange={e => updateCell(ri, c.key, e.target.value)}
                        />
                      </td>
                    ))}
                    <td style={{ ...tdStyle, textAlign: 'center' }}>
                      <button
                        onClick={() => deleteRow(ri)}
                        style={{
                          background: 'none', border: 'none', color: '#dc2626',
                          cursor: 'pointer', fontSize: 16, padding: '2px 6px',
                        }}
                        title="Delete row"
                      >
                        ✕
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Results ──────────────────────────────────────────────── */}
      {hasResults && (
        <>
          <div style={{ display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap' }}>
            <button onClick={downloadExcel} style={{ ...btnStyle, backgroundColor: '#2563eb' }}>
              Download Excel Report
            </button>
            {markdownReport && (
              <button onClick={copyMarkdown} style={{
                ...btnStyle, backgroundColor: copied ? '#059669' : '#374151'
              }}>
                {copied ? 'Copied!' : 'Copy Markdown Table'}
              </button>
            )}
            <button onClick={clearOutputs} disabled={clearing} style={{
              ...btnStyle, backgroundColor: clearing ? '#9ca3af' : '#dc2626'
            }}>
              {clearing ? 'Clearing...' : 'Clear Outputs'}
            </button>
          </div>

          {markdownReport && (
            <div style={{ marginBottom: 28 }}>
              <h2 style={{ fontSize: 15, marginBottom: 8 }}>Verification Report (Markdown)</h2>
              <pre style={{
                backgroundColor: '#f3f4f6', padding: 14, borderRadius: 8,
                overflowX: 'auto', fontSize: 12, lineHeight: 1.5,
                border: '1px solid #e5e7eb', whiteSpace: 'pre-wrap', wordBreak: 'break-all',
              }}>
                {markdownReport}
              </pre>
            </div>
          )}

          {/* Existing */}
          {existing.length > 0 && (
            <>
              <h2 style={{ fontSize: 15, marginBottom: 8, color: '#059669' }}>
                Existing SKUs ({existing.length})
              </h2>
              <div style={{ overflowX: 'auto', marginBottom: 28 }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
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
                    {existing.map((it, i) => (
                      <tr key={i} style={{ borderBottom: '1px solid #e5e7eb' }}>
                        <td style={tdStyle}>{it.sku}</td>
                        <td style={tdStyle}>{it.barcode || '—'}</td>
                        <td style={tdStyle}>{it.product_name || '—'}</td>
                        <td style={tdStyle}>{it.category || '—'}</td>
                        <td style={tdStyle}>{it.price || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}

          {/* Missing */}
          {missing.length > 0 && (
            <>
              <h2 style={{ fontSize: 15, marginBottom: 8, color: '#dc2626' }}>
                Missing SKUs ({missing.length})
              </h2>
              <div style={{ overflowX: 'auto', marginBottom: 28 }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                  <thead>
                    <tr style={{ backgroundColor: '#fef2f2' }}>
                      <th style={thStyle}>SKU Missing</th>
                      <th style={thStyle}>Barcode</th>
                      <th style={thStyle}>Product Name</th>
                      <th style={thStyle}>Category Name</th>
                      <th style={{ ...thStyle, minWidth: 250 }}>Noted</th>
                    </tr>
                  </thead>
                  <tbody>
                    {missing.map((it, i) => (
                      <tr key={i} style={{
                        borderBottom: '1px solid #e5e7eb',
                        backgroundColor: i % 2 === 0 ? '#fff' : '#fef2f2',
                      }}>
                        <td style={{ ...tdStyle, fontFamily: 'monospace' }}>{it.sku_missing}</td>
                        <td style={tdStyle}>{it.barcode}</td>
                        <td style={tdStyle}>{it.product_name}</td>
                        <td style={tdStyle}>{it.category_name}</td>
                        <td style={{ ...tdStyle, ...notedColor(it.noted) }}>{it.noted}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </>
      )}
    </div>
  )
}

export default App
