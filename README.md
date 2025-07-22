# OTC Binary Trading Prediction Tool

A personal tool for capturing OTC binary trading data visually from platforms like Quotex, storing historical patterns, and predicting future candle directions using machine learning.

## Overview

This project aims to create a personal assistant for binary options trading by:
1. Visually capturing candle data from trading platforms (no API required)
2. Storing and analyzing historical patterns
3. Predicting future market movements based on similar patterns
4. Providing a user-friendly dashboard to display predictions and control the bot

## Features

### Browser Automation
- Automated screen capture of trading charts
- Visual data extraction using OCR/image processing
- Detection of candle direction, price movements, and timing

### Data Storage
- MongoDB database for historical candle data
- Pattern storage and indexing for quick retrieval
- Duplicate prevention and data validation

### Pattern Recognition
- Machine learning models to identify recurring patterns
- Prediction of next candle direction with confidence level
- Comparison with similar historical patterns

### Web Dashboard
- React/Next.js frontend for monitoring and control
- Live view of trading platform
- Historical data visualization
- Prediction display with confidence metrics
- Bot control interface

## Tech Stack
- **Frontend**: React/Next.js, Material-UI, Recharts
- **Backend**: Node.js, Express
- **Database**: MongoDB with Mongoose
- **Browser Automation**: Puppeteer/Playwright
- **OCR/Image Processing**: Tesseract.js, Sharp
- **Machine Learning**: brain.js or scikit-learn

## Getting Started

### Prerequisites
- Node.js (v16+)
- MongoDB
- Git

### Installation

1. Clone the repository
```bash
git clone https://github.com/yourusername/otc-predictor.git
cd otc-predictor
```

2. Install dependencies
```bash
npm install
```

3. Configure environment variables
```bash
cp .env.example .env
```
Edit the `.env` file with your specific configuration.

4. Start the development server
```bash
npm run dev
```

## Usage

1. Open the dashboard in your browser at `http://localhost:3000`
2. Configure the bot settings (trading pair, timeframe, etc.)
3. Click "Start Bot" to begin data collection
4. View predictions on the dashboard as they become available
5. Review historical data and pattern matches in the History tab

## Project Structure
```
otc-predictor/
├── backend/
│   ├── scraper/            # Puppeteer scripts
│   ├── extract/            # Tesseract/OpenCV for image parsing
│   ├── model/              # ML logic and predictions
│   ├── db/                 # MongoDB connection and schema
│   └── server.js           # API endpoints
├── frontend/
│   ├── components/
│   ├── pages/
│   └── dashboard.jsx       # React dashboard UI
├── shared/
│   └── utils.js
├── memory-bank/            # Project documentation
├── .env                    # Environment variables
├── package.json
└── README.md
```

## Development Roadmap

- [x] Project setup and structure
- [ ] Backend framework and database setup
- [ ] Browser automation and screenshot capture
- [ ] OCR/image processing pipeline
- [ ] Data storage and pattern indexing
- [ ] Machine learning model implementation
- [ ] API endpoint development
- [ ] Frontend dashboard creation
- [ ] System integration and testing
- [ ] Performance optimization

## Disclaimer

This tool is for personal educational purposes only. Trading binary options involves significant risk. This project is not financial advice, and the predictions should not be the sole basis for trading decisions. Always use proper risk management.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
