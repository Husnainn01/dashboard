# 🚀 Separate Frontend & Backend Setup Guide

## ✅ **What Changed**

**Before (Monorepo Issue):**
- ❌ One `package.json` file in root with ALL dependencies
- ❌ `npm run dev` runs both frontend and backend together
- ❌ Cannot deploy backend separately to Railway

**Now (Separate Projects):**
- ✅ Separate `package.json` files for frontend and backend
- ✅ Run each project independently 
- ✅ Perfect for separate deployment (Railway backend)

## 📁 **New Project Structure**

```
otc-predictor/
├── backend/
│   ├── package.json           # 🆕 Backend-only dependencies
│   ├── node_modules/          # Backend dependencies
│   ├── server.js
│   ├── routes/
│   ├── services/
│   └── models/
├── frontend/
│   ├── package.json           # 🆕 Frontend-only dependencies
│   ├── node_modules/          # Frontend dependencies
│   ├── pages/
│   ├── components/
│   └── styles/
└── package.json               # Root workspace commands
```

## 🔧 **How to Run Separately**

### **Backend Only** (Express API)
```bash
# Navigate to backend
cd backend

# Install dependencies (first time)
npm install

# Run in development mode
npm run dev

# Or run in production mode
npm start

# The backend will run on: http://localhost:5001
```

### **Frontend Only** (Next.js Dashboard)
```bash
# Navigate to frontend
cd frontend

# Install dependencies (first time)
npm install

# Run in development mode
npm run dev

# Build for production
npm run build

# Run production build
npm start

# The frontend will run on: http://localhost:3000
```

### **Workspace Commands** (From Root)
```bash
# Install all dependencies
npm run install:all

# Run backend from root
npm run dev:backend

# Run frontend from root
npm run dev:frontend

# Build frontend from root
npm run build:frontend
```

## 📦 **Dependencies Split**

### **Backend Dependencies**
- ✅ `express` - API server
- ✅ `mongoose` - MongoDB connection
- ✅ `puppeteer` - Screen capture
- ✅ `cloudinary` - Screenshot storage
- ✅ `cors` - Cross-origin requests
- ✅ `dotenv` - Environment variables
- ✅ `brain.js` - ML predictions
- ✅ `nodemon` - Development auto-restart

### **Frontend Dependencies**
- ✅ `next` - React framework
- ✅ `react` & `react-dom` - UI library
- ✅ `@mui/material` - UI components
- ✅ `@emotion/react` - Styling
- ✅ `axios` - HTTP requests
- ✅ `recharts` - Charts/graphs
- ✅ `eslint-config-next` - Linting

## 🚀 **Development Workflow**

### **1. Daily Development**
```bash
# Terminal 1: Start backend
cd backend && npm run dev

# Terminal 2: Start frontend
cd frontend && npm run dev
```

### **2. Backend Testing** (Railway Deployment)
```bash
cd backend
npm start
# Test API endpoints at http://localhost:5001
```

### **3. Frontend Testing** (Vercel Deployment)
```bash
cd frontend
npm run build
npm start
# Test production build at http://localhost:3000
```

## 🌐 **Railway Deployment** (Backend Only)

### **Option 1: Direct Deploy**
1. In Railway, connect your GitHub repo
2. Set **Root Directory**: `backend`
3. Railway auto-detects `package.json` in backend folder
4. Environment variables: `MONGO_URI`, `CLOUDINARY_URL`

### **Option 2: Manual Deploy**
```bash
cd backend
# Railway will use the backend/package.json file
railway login
railway link
railway up
```

## 🔧 **Environment Variables**

### **Backend (.env in backend folder)**
```bash
MONGO_URI=mongodb+srv://dash:JBuim9uQ8CbXPd1K@dashbaord.zsslbre.mongodb.net
CLOUDINARY_URL=cloudinary://147728226681618:vF6gOcx-ciCR3rJMsn2XmYGtPI8@dxttfrplr
PORT=5001
NODE_ENV=development
```

### **Frontend** (Optional .env.local in frontend folder)
```bash
NEXT_PUBLIC_API_URL=http://localhost:5001  # Development
# NEXT_PUBLIC_API_URL=https://your-backend.railway.app  # Production
```

## 📝 **Package.json Scripts Explained**

### **Backend Scripts**
- `npm start` - Production server
- `npm run dev` - Development with auto-restart
- `npm test` - Run tests
- `npm run lint` - Check code style

### **Frontend Scripts**
- `npm run dev` - Development server
- `npm run build` - Build for production
- `npm start` - Serve production build
- `npm run lint` - Check code style

### **Root Workspace Scripts**
- `npm run dev:backend` - Start backend from root
- `npm run dev:frontend` - Start frontend from root  
- `npm run install:all` - Install all dependencies
- `npm run clean` - Remove all node_modules

## ✅ **Benefits of This Setup**

1. **🎯 Focused Development**: Work on frontend or backend independently
2. **🚀 Separate Deployment**: Deploy backend to Railway, frontend to Vercel
3. **📦 Optimized Dependencies**: Each project only has what it needs
4. **⚡ Faster Installs**: Smaller dependency trees
5. **🔧 Better Debugging**: Clear separation of concerns
6. **🌐 Production Ready**: Industry-standard project structure

## 🎉 **You're All Set!**

Now you can:
- ✅ Run backend separately for Railway deployment
- ✅ Run frontend separately for development/testing
- ✅ Deploy each project to different platforms
- ✅ Work on each part independently

**Happy coding!** 🚀 