const express = require('express');
const cors = require('cors');
const mongoose = require('mongoose');
const net = require('net');
require('dotenv').config();

const authRoutes = require('./routes/auth');
const dataRoutes = require('./routes/data'); // Add data routes
const screenshotRoutes = require('./routes/screenshots'); // Add screenshot routes

const app = express();
const DEFAULT_PORT = process.env.PORT || 5001;

console.log('Starting OTC Predictor API Server');
console.log(`Node environment: ${process.env.NODE_ENV || 'development'}`);

// Middleware
app.use(cors({
  origin: process.env.FRONTEND_URL || 'http://localhost:3000',
  credentials: true
}));
app.use(express.json({ limit: '10mb' })); // Increase limit for screenshot data
app.use(express.urlencoded({ extended: true }));

// MongoDB Connection
const MONGO_URI = process.env.MONGO_URI || process.env.MONGODB_URI || 'mongodb+srv://dash:JBuim9uQ8CbXPd1K@dashbaord.zsslbre.mongodb.net/otc-predictor';
console.log(`Attempting to connect to MongoDB...`);
console.log(`MongoDB URI: ${MONGO_URI.replace(/\/\/([^:]+):([^@]+)@/, '//***:***@')}`); // Hide credentials in logs

// Disable Mongoose buffering for better error handling
mongoose.set('bufferCommands', false);

mongoose.connect(MONGO_URI, {
  serverSelectionTimeoutMS: 10000, // 10 seconds
  maxPoolSize: 10, // Maximum number of connections
  minPoolSize: 2, // Minimum number of connections
  maxIdleTimeMS: 30000, // Close connections after 30 seconds of inactivity
})
.then(() => {
  console.log('✅ MongoDB connected successfully');
  console.log(`Database: ${mongoose.connection.name}`);
  console.log(`Host: ${mongoose.connection.host}:${mongoose.connection.port}`);
})
.catch(err => {
  console.error('❌ MongoDB connection error:', err.message);
  console.error('Stack trace:', err.stack);
  
  // For Atlas connection issues, provide helpful debug info
  if (err.message.includes('ENOTFOUND')) {
    console.error('🔍 Debug: DNS resolution failed. Check your MongoDB Atlas connection string.');
  } else if (err.message.includes('authentication failed')) {
    console.error('🔍 Debug: Authentication failed. Check your MongoDB Atlas username and password.');
  } else if (err.message.includes('network timeout')) {
    console.error('🔍 Debug: Network timeout. Check your network connection and MongoDB Atlas whitelist.');
  }
});

// MongoDB connection events
mongoose.connection.on('connected', () => {
  console.log('📡 Mongoose connected to MongoDB');
});

mongoose.connection.on('error', (err) => {
  console.error('❌ Mongoose connection error:', err);
});

mongoose.connection.on('disconnected', () => {
  console.log('📴 Mongoose disconnected from MongoDB');
});

// Graceful shutdown
process.on('SIGINT', async () => {
  try {
    console.log('🔄 Gracefully shutting down...');
    await mongoose.connection.close();
    console.log('✅ MongoDB connection closed');
    process.exit(0);
  } catch (error) {
    console.error('❌ Error during shutdown:', error);
    process.exit(1);
  }
});

// Health check endpoint
app.get('/api/health', async (req, res) => {
  console.log('Health check endpoint called');
  
  try {
    // Check MongoDB connection
    const dbStatus = mongoose.connection.readyState === 1 ? 'connected' : 'disconnected';
    
    const healthData = {
      status: 'OK',
      message: 'Server is running',
      timestamp: new Date().toISOString(),
      database: {
        status: dbStatus,
        name: mongoose.connection.name || 'not connected'
      },
      version: process.env.npm_package_version || '1.0.0'
    };
    
    res.status(200).json(healthData);
  } catch (error) {
    console.error('Health check error:', error);
    res.status(500).json({
      status: 'ERROR',
      message: 'Health check failed',
      error: error.message
    });
  }
});

// API Routes
app.use('/api/auth', authRoutes);
app.use('/api/data', dataRoutes); // Add data routes
app.use('/api/screenshots', screenshotRoutes); // Add screenshot routes

// Root endpoint
app.get('/', (req, res) => {
  res.json({ 
    message: 'OTC Predictor API Server',
    version: '1.0.0',
    endpoints: [
      '/api/health',
      '/api/auth/*',
      '/api/data/*'
    ]
  });
});

// Global error handler
app.use((err, req, res, next) => {
  console.error('Global error handler caught error:', err);
  console.error('Error stack:', err.stack);
  
  res.status(err.status || 500).json({
    success: false,
    message: 'An unexpected error occurred',
    error: process.env.NODE_ENV === 'development' ? {
      message: err.message,
      stack: err.stack
    } : 'Internal server error'
  });
});

// 404 handler
app.use('*', (req, res) => {
  res.status(404).json({
    success: false,
    message: `Route ${req.originalUrl} not found`
  });
});

// Check if port is in use
function isPortInUse(port) {
  return new Promise((resolve) => {
    const server = net.createServer()
      .once('error', () => resolve(true))
      .once('listening', () => {
        server.close();
        resolve(false);
      })
      .listen(port);
  });
}

// Start server with port checking
async function startServer(startPort, maxAttempts = 10) {
  let currentPort = startPort;
  let attempts = 0;

  while (attempts < maxAttempts) {
    const portInUse = await isPortInUse(currentPort);
    
    if (!portInUse) {
      app.listen(currentPort, () => {
        console.log(`🚀 Server running on port ${currentPort}`);
        console.log(`📍 Local: http://localhost:${currentPort}`);
        console.log(`🌐 Network: http://0.0.0.0:${currentPort}`);
        console.log('📚 API Documentation: /api/health');
        console.log('⏰ Server started at:', new Date().toISOString());
      });
      return;
    }

    console.log(`⚠️  Port ${currentPort} is already in use, trying ${currentPort + 1}...`);
    currentPort++;
    attempts++;
  }

  console.error(`❌ Could not find an available port after ${maxAttempts} attempts`);
  process.exit(1);
}

// Handle unhandled promise rejections
process.on('unhandledRejection', (reason, promise) => {
  console.error('❌ Unhandled Rejection at:', promise, 'reason:', reason);
});

process.on('uncaughtException', (error) => {
  console.error('❌ Uncaught Exception:', error);
  console.error('Stack trace:', error.stack);
});

// Start the server
startServer(DEFAULT_PORT);

module.exports = app;
