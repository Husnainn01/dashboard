import React, { useState } from 'react';
import {
  Paper,
  Typography,
  Box,
  IconButton,
  Divider,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TablePagination,
  Tabs,
  Tab,
  Chip
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import DownloadIcon from '@mui/icons-material/Download';
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward';
import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward';
import { format } from 'date-fns';

/**
 * HistoryPanel Component
 * Displays historical candle data and predictions
 */
const HistoryPanel = ({ candles, predictions = [], onClose }) => {
  const [tab, setTab] = useState(0);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  
  // Handle tab change
  const handleTabChange = (event, newValue) => {
    setTab(newValue);
    setPage(0);
  };
  
  // Handle page change
  const handleChangePage = (event, newPage) => {
    setPage(newPage);
  };
  
  // Handle rows per page change
  const handleChangeRowsPerPage = (event) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };
  
  // Format timestamp
  const formatTimestamp = (timestamp) => {
    try {
      return format(new Date(timestamp), 'yyyy-MM-dd HH:mm:ss');
    } catch (error) {
      return timestamp;
    }
  };
  
  // Export to CSV
  const exportToCSV = () => {
    // Generate CSV content
    const headers = ['Timestamp', 'Open', 'Close', 'High', 'Low', 'Direction'];
    const csvContent = [
      headers.join(','),
      ...candles.map(candle => [
        formatTimestamp(candle.timestamp),
        candle.open,
        candle.close,
        candle.high,
        candle.low,
        candle.direction
      ].join(','))
    ].join('\n');
    
    // Create download link
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `candle-data-${new Date().toISOString().slice(0, 10)}.csv`;
    
    // Trigger download
    document.body.appendChild(link);
    link.click();
    
    // Clean up
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };
  
  return (
    <Paper sx={{ p: 2, mb: 2 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6">Historical Data</Typography>
        <Box>
          <IconButton onClick={exportToCSV} title="Export to CSV">
            <DownloadIcon />
          </IconButton>
          <IconButton onClick={onClose} title="Close">
            <CloseIcon />
          </IconButton>
        </Box>
      </Box>
      
      <Divider sx={{ mb: 2 }} />
      
      <Tabs value={tab} onChange={handleTabChange} sx={{ mb: 2 }}>
        <Tab label="Candle Data" />
        <Tab label="Predictions" />
        <Tab label="Statistics" />
      </Tabs>
      
      {tab === 0 && (
        <>
          <TableContainer className="history-table-container">
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>#</TableCell>
                  <TableCell>Timestamp</TableCell>
                  <TableCell>Direction</TableCell>
                  <TableCell>Open</TableCell>
                  <TableCell>Close</TableCell>
                  <TableCell>High</TableCell>
                  <TableCell>Low</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {(candles || [])
                  .slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage)
                  .map((candle, index) => (
                    <TableRow key={index} sx={{ '&:last-child td, &:last-child th': { border: 0 } }}>
                      <TableCell>{page * rowsPerPage + index + 1}</TableCell>
                      <TableCell>{formatTimestamp(candle.timestamp)}</TableCell>
                      <TableCell>
                        {candle.direction === 'up' ? (
                          <Chip 
                            icon={<ArrowUpwardIcon />} 
                            label="UP" 
                            size="small" 
                            color="success"
                          />
                        ) : (
                          <Chip 
                            icon={<ArrowDownwardIcon />} 
                            label="DOWN" 
                            size="small" 
                            color="error"
                          />
                        )}
                      </TableCell>
                      <TableCell>{candle.open?.toFixed(5)}</TableCell>
                      <TableCell>{candle.close?.toFixed(5)}</TableCell>
                      <TableCell>{candle.high?.toFixed(5)}</TableCell>
                      <TableCell>{candle.low?.toFixed(5)}</TableCell>
                    </TableRow>
                  ))}
              </TableBody>
            </Table>
          </TableContainer>
          
          <TablePagination
            rowsPerPageOptions={[10, 25, 50, 100]}
            component="div"
            count={candles?.length || 0}
            rowsPerPage={rowsPerPage}
            page={page}
            onPageChange={handleChangePage}
            onRowsPerPageChange={handleChangeRowsPerPage}
          />
        </>
      )}
      
      {tab === 1 && (
        <Box sx={{ p: 2, textAlign: 'center' }}>
          <Typography>
            {predictions.length > 0 
              ? 'Prediction history would be displayed here'
              : 'No prediction data available yet'}
          </Typography>
        </Box>
      )}
      
      {tab === 2 && (
        <Box sx={{ p: 2 }}>
          <Typography variant="h6" gutterBottom>Summary Statistics</Typography>
          
          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2 }}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="subtitle1">Candle Direction</Typography>
              <Divider sx={{ my: 1 }} />
              
              {candles && candles.length > 0 ? (
                <>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 2 }}>
                    <Typography>Up candles:</Typography>
                    <Typography>
                      {candles.filter(c => c.direction === 'up').length} 
                      ({Math.round(candles.filter(c => c.direction === 'up').length / candles.length * 100)}%)
                    </Typography>
                  </Box>
                  
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 1 }}>
                    <Typography>Down candles:</Typography>
                    <Typography>
                      {candles.filter(c => c.direction === 'down').length}
                      ({Math.round(candles.filter(c => c.direction === 'down').length / candles.length * 100)}%)
                    </Typography>
                  </Box>
                </>
              ) : (
                <Typography sx={{ mt: 2 }}>No candle data available</Typography>
              )}
            </Paper>
            
            <Paper sx={{ p: 2 }}>
              <Typography variant="subtitle1">Price Movement</Typography>
              <Divider sx={{ my: 1 }} />
              
              {candles && candles.length > 0 ? (
                <>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 2 }}>
                    <Typography>Min price:</Typography>
                    <Typography>
                      {Math.min(...candles.map(c => c.low)).toFixed(5)}
                    </Typography>
                  </Box>
                  
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 1 }}>
                    <Typography>Max price:</Typography>
                    <Typography>
                      {Math.max(...candles.map(c => c.high)).toFixed(5)}
                    </Typography>
                  </Box>
                  
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 1 }}>
                    <Typography>Average movement:</Typography>
                    <Typography>
                      {(candles.reduce((sum, c) => sum + Math.abs(c.close - c.open), 0) / candles.length).toFixed(5)}
                    </Typography>
                  </Box>
                </>
              ) : (
                <Typography sx={{ mt: 2 }}>No candle data available</Typography>
              )}
            </Paper>
          </Box>
        </Box>
      )}
    </Paper>
  );
};

export default HistoryPanel; 