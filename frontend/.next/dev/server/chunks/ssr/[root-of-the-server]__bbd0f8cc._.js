module.exports = [
"[project]/frontend/services/api.js [ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "createMarketDataWebSocket",
    ()=>createMarketDataWebSocket,
    "createPredictionWebSocket",
    ()=>createPredictionWebSocket,
    "createUnifiedWebSocket",
    ()=>createUnifiedWebSocket,
    "default",
    ()=>__TURBOPACK__default__export__,
    "fetchLatestCandles",
    ()=>fetchLatestCandles,
    "getDataCollectionStatus",
    ()=>getDataCollectionStatus,
    "getDatabaseStats",
    ()=>getDatabaseStats,
    "getHealthStatus",
    ()=>getHealthStatus,
    "getLatestPrediction",
    ()=>getLatestPrediction,
    "getModelsForPair",
    ()=>getModelsForPair,
    "getModelsInfo",
    ()=>getModelsInfo,
    "getPredictionAccuracy",
    ()=>getPredictionAccuracy,
    "getServiceStatuses",
    ()=>getServiceStatuses,
    "getSystemStatus",
    ()=>getSystemStatus,
    "getTradingPairs",
    ()=>getTradingPairs,
    "getTrainingQueueStatus",
    ()=>getTrainingQueueStatus,
    "getTrainingStatus",
    ()=>getTrainingStatus,
    "requestPrediction",
    ()=>requestPrediction,
    "retrainModel",
    ()=>retrainModel,
    "selectModel",
    ()=>selectModel,
    "setApiBaseUrl",
    ()=>setApiBaseUrl,
    "setWsBaseUrl",
    ()=>setWsBaseUrl,
    "startPredictionService",
    ()=>startPredictionService,
    "stopPredictionService",
    ()=>stopPredictionService
]);
/**
 * API Service
 * Provides functions to communicate with the OTC Predictor API Gateway
 * Updated for microservices architecture
 *
 * All HTTP requests go through Next.js rewrites (server-side proxy) to
 * avoid CORS issues.  The browser only hits /api/*, /ml-api/*, /data-api/*
 * which Next.js forwards to the actual Railway URLs configured in .env.
 *
 * WebSocket URLs still connect directly (WSS doesn't go through rewrites).
 */ // HTTP proxy paths (matched by next.config.js rewrites)
const API_BASE = '/api'; // → NEXT_PUBLIC_API_URL
const ML_TRAINING_BASE = '/ml-api'; // → NEXT_PUBLIC_ML_TRAINING_URL
const DATA_COLLECTION_BASE = '/data-api'; // → NEXT_PUBLIC_DATA_COLLECTION_URL
const getApiBase = ()=>API_BASE;
// WebSocket still needs the direct URL (can't proxy through Next.js rewrites)
const getWsBase = ()=>{
    if ("TURBOPACK compile-time falsy", 0) //TURBOPACK unreachable
    ;
    return ("TURBOPACK compile-time value", "wss://api-gateway-production-6d82.up.railway.app") || '';
};
const setApiBaseUrl = ()=>{};
const setWsBaseUrl = (url)=>{
    if ("TURBOPACK compile-time falsy", 0) //TURBOPACK unreachable
    ;
};
console.log('🔌 API proxy path:', API_BASE);
console.log('📡 WebSocket base:', getWsBase() || '(unset)');
/**
 * Generic API request handler with error handling
 * @param {string} endpoint - API endpoint
 * @param {Object} options - Fetch options
 * @returns {Promise<Object>} API response
 */ const apiRequest = async (endpoint, options = {})=>{
    try {
        // Add cache-busting parameter for GET requests
        const cacheBuster = options.method === 'GET' ? `${endpoint.includes('?') ? '&' : '?'}_t=${Date.now()}` : '';
        // Construct full URL
        const url = `${getApiBase()}${endpoint}${cacheBuster}`;
        console.log(`🔌 API Request: ${options.method || 'GET'} ${url}`);
        // Set default headers
        const headers = {
            'Content-Type': 'application/json',
            ...options.headers
        };
        // Make request
        const response = await fetch(url, {
            ...options,
            headers
        });
        // Handle non-200 responses
        if (!response.ok) {
            const errorText = await response.text();
            let detail = '';
            try {
                detail = JSON.parse(errorText)?.message || errorText;
            } catch  {
                detail = errorText;
            }
            console.error(`❌ API Error (${response.status}): ${detail}`);
            throw new Error(`${response.status}: ${detail || response.statusText}`);
        }
        // Parse JSON response
        const data = await response.json();
        return data;
    } catch (error) {
        console.error('❌ API Request failed:', error);
        throw error;
    }
};
/**
 * Make a direct request to the ML Training Service (bypassing API Gateway)
 * @param {string} endpoint - ML Training service endpoint
 * @param {Object} options - Fetch options
 * @returns {Promise<Object>} Response data
 */ const directMLTrainingRequest = async (endpoint, options = {})=>{
    try {
        // Add cache-busting parameter for GET requests
        const cacheBuster = options.method === 'GET' ? `${endpoint.includes('?') ? '&' : '?'}_t=${Date.now()}` : '';
        const url = `${ML_TRAINING_BASE}${endpoint}${cacheBuster}`;
        console.log(`🔄 Direct ML Training Request: ${options.method || 'GET'} ${url}`);
        const response = await fetch(url, {
            headers: {
                'Content-Type': 'application/json',
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Pragma': 'no-cache',
                ...options.headers
            },
            ...options
        });
        // Handle non-200 responses
        if (!response.ok) {
            const errorText = await response.text();
            console.error(`❌ ML Training API Error (${response.status}): ${errorText}`);
            throw new Error(`ML Training API Error: ${response.status} ${errorText}`);
        }
        // Parse JSON response
        const data = await response.json();
        console.log('✅ ML Training API Response:', data);
        return data;
    } catch (error) {
        console.error(`❌ ML Training API Error: ${endpoint}`, error.message);
        throw error;
    }
};
const getHealthStatus = async ()=>{
    return await apiRequest('/health');
};
const getSystemStatus = async ()=>{
    return await apiRequest('/status');
};
const getDatabaseStats = async ()=>{
    return await apiRequest('/database/stats');
};
const fetchLatestCandles = async (params = {})=>{
    const tradingPair = encodeURIComponent(params.trading_pair || 'USD/BRL(OTC)');
    const limit = params.limit || 50;
    return await apiRequest(`/data/candles/${tradingPair}?limit=${limit}`);
};
const getLatestPrediction = async (tradingPair = 'USD/BRL(OTC)', modelType = null, modelName = null)=>{
    let queryParams = [];
    if (modelName) {
        queryParams.push(`model_name=${encodeURIComponent(modelName)}`);
    }
    if (modelType) {
        queryParams.push(`model_type=${encodeURIComponent(modelType)}`);
    }
    const qp = queryParams.length > 0 ? `?${queryParams.join('&')}` : '';
    return await apiRequest(`/predict/${encodeURIComponent(tradingPair)}${qp}`);
};
const requestPrediction = async (tradingPair = 'USD/BRL(OTC)', modelType = null, modelName = null)=>{
    const body = {
        trading_pair: tradingPair
    };
    if (modelType) {
        body.model_type = modelType;
    }
    if (modelName) {
        body.model_name = modelName;
    }
    return await apiRequest('/predict', {
        method: 'POST',
        body: JSON.stringify(body)
    });
};
const getModelsInfo = async ()=>{
    return await apiRequest('/ml/models');
};
const getModelsForPair = async (tradingPair)=>{
    try {
        console.log(`🔍 Fetching models for pair: ${tradingPair}`);
        const data = await apiRequest(`/ml/models/${encodeURIComponent(tradingPair)}`);
        console.log('✅ Models fetched successfully:', data);
        return data;
    } catch (error) {
        console.error('❌ Error fetching models:', error);
        return {
            local_models: [],
            cloud_models: []
        };
    }
};
const retrainModel = async (tradingPair = 'USD/BRL(OTC)', modelType = 'xgboost', forceRetrain = false)=>{
    // Special handling for LightGBM model type - direct API call to ML training service
    if (modelType.toLowerCase() === 'lightgbm') {
        console.log('🔄 Using direct API call for LightGBM model training');
        return await directMLTrainingRequest('/train', {
            method: 'POST',
            body: JSON.stringify({
                trading_pair: tradingPair,
                model_type: modelType,
                force_retrain: forceRetrain
            })
        });
    }
    // Normal API Gateway call for other model types
    return await apiRequest('/ml/train', {
        method: 'POST',
        body: JSON.stringify({
            trading_pair: tradingPair,
            model_type: modelType,
            force_retrain: forceRetrain
        })
    });
};
const getTrainingStatus = async (jobId)=>{
    return await apiRequest(`/ml/train/status/${jobId}`);
};
const getTrainingQueueStatus = async ()=>{
    return await apiRequest('/ml/queue/status');
};
const getTradingPairs = async ()=>{
    return await apiRequest('/trading-pairs');
};
const startPredictionService = async ()=>{
    return await apiRequest('/predictions/start', {
        method: 'POST'
    });
};
const stopPredictionService = async ()=>{
    return await apiRequest('/predictions/stop', {
        method: 'POST'
    });
};
const selectModel = async (tradingPair, modelName, modelType = null)=>{
    const payload = {
        trading_pair: tradingPair,
        model_name: modelName,
        model_type: modelType
    };
    const attempt = async ()=>await apiRequest('/predictions/select_model', {
            method: 'POST',
            body: JSON.stringify(payload)
        });
    try {
        return await attempt();
    } catch (err) {
        console.warn('⚠️ selectModel failed, retrying in 1s...', err?.message || err);
        await new Promise((r)=>setTimeout(r, 1000));
        return await attempt();
    }
};
const getServiceStatuses = async ()=>{
    const health = await getHealthStatus();
    return health.services;
};
const getPredictionAccuracy = async ()=>{
    return await apiRequest('/api/predictions/accuracy');
};
const getDataCollectionStatus = async ()=>{
    const response = await fetch(`${DATA_COLLECTION_BASE}/status`);
    return response.json();
};
const createPredictionWebSocket = ()=>new WebSocket(`${getWsBase()}/ws/predictions`);
const createMarketDataWebSocket = ()=>new WebSocket(`${getWsBase()}/ws/market-data`);
const createUnifiedWebSocket = ()=>new WebSocket(`${getWsBase()}/ws`);
const __TURBOPACK__default__export__ = {
    // System Status
    getHealthStatus,
    getSystemStatus,
    getDatabaseStats,
    // Candle Data
    fetchLatestCandles,
    // ML Predictions
    getLatestPrediction,
    requestPrediction,
    // Model Management
    getModelsInfo,
    getModelsForPair,
    retrainModel,
    getTrainingStatus,
    getTrainingQueueStatus,
    getTradingPairs,
    // Prediction Service Control
    startPredictionService,
    stopPredictionService,
    selectModel,
    // Service Status & Accuracy
    getServiceStatuses,
    getPredictionAccuracy,
    getDataCollectionStatus,
    // WebSocket Connections
    createPredictionWebSocket,
    createMarketDataWebSocket,
    createUnifiedWebSocket
};
}),
"[project]/frontend/components/SidePanel.jsx [ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>SidePanel
]);
var __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__ = __turbopack_context__.i("[externals]/react/jsx-dev-runtime [external] (react/jsx-dev-runtime, cjs)");
var __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__ = __turbopack_context__.i("[externals]/react [external] (react, cjs)");
var __TURBOPACK__imported__module__$5b$project$5d2f$frontend$2f$services$2f$api$2e$js__$5b$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/frontend/services/api.js [ssr] (ecmascript)");
;
;
;
const DEFAULT_PAIRS = [
    {
        value: 'USD/BRL(OTC)',
        label: 'USD/BRL OTC',
        flag: '🇺🇸🇧🇷'
    }
];
function SidePanel({ selectedPair, onPairChange, selectedModel, onModelChange, predictionActive, setPredictionActive }) {
    const [pairs, setPairs] = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__["useState"])(DEFAULT_PAIRS);
    const [loadingModels, setLoadingModels] = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__["useState"])(false);
    const [models, setModels] = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__["useState"])([]);
    const [isTraining, setIsTraining] = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__["useState"])(false);
    const [trainMsg, setTrainMsg] = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__["useState"])(null);
    const [serviceBusy, setServiceBusy] = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__["useState"])(false);
    const [trainingAlgo, setTrainingAlgo] = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__["useState"])(null);
    // Fetch trading pairs from API on mount
    (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__["useEffect"])(()=>{
        const fetchPairs = async ()=>{
            try {
                const data = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$frontend$2f$services$2f$api$2e$js__$5b$ssr$5d$__$28$ecmascript$29$__["getTradingPairs"])();
                if (data?.trading_pairs?.length) {
                    setPairs(data.trading_pairs.map((p)=>({
                            value: p,
                            label: p.replace('_otc', ' OTC').replace('_', '/'),
                            flag: ''
                        })));
                }
            } catch (e) {
                console.warn('Failed to fetch trading pairs, using defaults', e);
            }
        };
        fetchPairs();
    }, []);
    // Load models when pair changes
    (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__["useEffect"])(()=>{
        if (!selectedPair) return;
        refreshModels();
    }, [
        selectedPair
    ]);
    const refreshModels = async ()=>{
        try {
            setLoadingModels(true);
            const data = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$frontend$2f$services$2f$api$2e$js__$5b$ssr$5d$__$28$ecmascript$29$__["getModelsForPair"])(selectedPair);
            const list = [];
            const inferAlgorithm = (m)=>{
                if (m.algorithm) return m.algorithm;
                const name = m.model_name || m.model_id || '';
                const prefix = String(name).toLowerCase();
                if (prefix.startsWith('lightgbm')) return 'lightgbm';
                if (prefix.startsWith('random_forest') || prefix.startsWith('randomforest')) return 'random_forest';
                if (prefix.startsWith('xgboost') || prefix.startsWith('xgb')) return 'xgboost';
                return 'xgboost';
            };
            (data.local_models || []).forEach((m)=>list.push({
                    id: m.model_id || m.model_name,
                    name: m.model_name || m.model_id,
                    algorithm: inferAlgorithm(m),
                    created_at: m.created_at || m.saved_at,
                    location: 'local'
                }));
            (data.cloud_models || []).forEach((m)=>list.push({
                    id: m.model_id || m.model_name,
                    name: m.model_name || m.model_id,
                    algorithm: inferAlgorithm(m),
                    created_at: m.created_at || m.saved_at,
                    location: 'cloud'
                }));
            list.sort((a, b)=>new Date(b.created_at || 0) - new Date(a.created_at || 0));
            setModels(list);
            if (!selectedModel && list.length) onModelChange(list[0]);
        } catch (e) {
            console.error('Failed loading models', e);
            setModels([]);
        } finally{
            setLoadingModels(false);
        }
    };
    const handleTrain = async (modelType = 'xgboost')=>{
        try {
            setIsTraining(true);
            setTrainingAlgo(modelType);
            setTrainMsg(`Submitting ${modelType} training job...`);
            const res = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$frontend$2f$services$2f$api$2e$js__$5b$ssr$5d$__$28$ecmascript$29$__["retrainModel"])(selectedPair, modelType);
            setTrainMsg(`Training started (${modelType})${res?.job_id ? ' · Job: ' + res.job_id : ''}`);
            // Poll models after a short delay
            setTimeout(refreshModels, 8000);
        } catch (e) {
            setTrainMsg(`Training failed (${modelType}): ${e.message}`);
        } finally{
            setTimeout(()=>setTrainMsg(null), 6000);
            setIsTraining(false);
            setTrainingAlgo(null);
        }
    };
    const handleSelectModel = async (modelId)=>{
        const model = models.find((m)=>m.id === modelId || m.name === modelId);
        if (!model) return;
        onModelChange(model);
        try {
            await (0, __TURBOPACK__imported__module__$5b$project$5d2f$frontend$2f$services$2f$api$2e$js__$5b$ssr$5d$__$28$ecmascript$29$__["selectModel"])(selectedPair, model.name, model.algorithm);
        } catch (e) {
            console.warn('Model select failed (will still keep local selection):', e?.message || e);
        }
    };
    const handleTogglePrediction = async ()=>{
        if (!selectedModel) return;
        try {
            setServiceBusy(true);
            if (predictionActive) {
                await (0, __TURBOPACK__imported__module__$5b$project$5d2f$frontend$2f$services$2f$api$2e$js__$5b$ssr$5d$__$28$ecmascript$29$__["stopPredictionService"])();
                setPredictionActive(false);
            } else {
                // Ensure selection persisted server-side before start
                try {
                    await (0, __TURBOPACK__imported__module__$5b$project$5d2f$frontend$2f$services$2f$api$2e$js__$5b$ssr$5d$__$28$ecmascript$29$__["selectModel"])(selectedPair, selectedModel.name, selectedModel.algorithm);
                } catch (_) {}
                await (0, __TURBOPACK__imported__module__$5b$project$5d2f$frontend$2f$services$2f$api$2e$js__$5b$ssr$5d$__$28$ecmascript$29$__["startPredictionService"])();
                setPredictionActive(true);
            }
        } catch (e) {
            console.error('Toggle prediction failed', e);
            alert(e?.message || 'Failed to toggle prediction');
        } finally{
            setServiceBusy(false);
        }
    };
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("aside", {
        className: "side-panel",
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                className: "sp-header",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                        className: "brand",
                        children: "OTC Predictor"
                    }, void 0, false, {
                        fileName: "[project]/frontend/components/SidePanel.jsx",
                        lineNumber: 155,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                        className: "subtitle",
                        children: "Netflix style"
                    }, void 0, false, {
                        fileName: "[project]/frontend/components/SidePanel.jsx",
                        lineNumber: 156,
                        columnNumber: 9
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/frontend/components/SidePanel.jsx",
                lineNumber: 154,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                className: "sp-section",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                        className: "sp-title",
                        children: "1. Select Pair"
                    }, void 0, false, {
                        fileName: "[project]/frontend/components/SidePanel.jsx",
                        lineNumber: 161,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("select", {
                        className: "sp-select",
                        value: selectedPair,
                        onChange: (e)=>onPairChange(e.target.value),
                        children: pairs.map((p)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("option", {
                                value: p.value,
                                children: [
                                    p.flag,
                                    " ",
                                    p.label
                                ]
                            }, p.value, true, {
                                fileName: "[project]/frontend/components/SidePanel.jsx",
                                lineNumber: 168,
                                columnNumber: 13
                            }, this))
                    }, void 0, false, {
                        fileName: "[project]/frontend/components/SidePanel.jsx",
                        lineNumber: 162,
                        columnNumber: 9
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/frontend/components/SidePanel.jsx",
                lineNumber: 160,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                className: "sp-section",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                        className: "sp-title",
                        children: "2. Train Model"
                    }, void 0, false, {
                        fileName: "[project]/frontend/components/SidePanel.jsx",
                        lineNumber: 177,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                        style: {
                            display: 'grid',
                            gap: 8
                        },
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("button", {
                                className: "sp-button primary",
                                onClick: ()=>handleTrain('xgboost'),
                                disabled: isTraining || serviceBusy,
                                children: isTraining && trainingAlgo === 'xgboost' ? 'Training…' : 'Train XGBoost'
                            }, void 0, false, {
                                fileName: "[project]/frontend/components/SidePanel.jsx",
                                lineNumber: 179,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("button", {
                                className: "sp-button",
                                onClick: ()=>handleTrain('lightgbm'),
                                disabled: isTraining || serviceBusy,
                                children: isTraining && trainingAlgo === 'lightgbm' ? 'Training…' : 'Train LightGBM'
                            }, void 0, false, {
                                fileName: "[project]/frontend/components/SidePanel.jsx",
                                lineNumber: 186,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("button", {
                                className: "sp-button",
                                onClick: ()=>handleTrain('random_forest'),
                                disabled: isTraining || serviceBusy,
                                children: isTraining && trainingAlgo === 'random_forest' ? 'Training…' : 'Train Random Forest'
                            }, void 0, false, {
                                fileName: "[project]/frontend/components/SidePanel.jsx",
                                lineNumber: 193,
                                columnNumber: 11
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/frontend/components/SidePanel.jsx",
                        lineNumber: 178,
                        columnNumber: 9
                    }, this),
                    trainMsg && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                        className: "sp-hint",
                        children: trainMsg
                    }, void 0, false, {
                        fileName: "[project]/frontend/components/SidePanel.jsx",
                        lineNumber: 201,
                        columnNumber: 22
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/frontend/components/SidePanel.jsx",
                lineNumber: 176,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                className: "sp-section",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                        className: "sp-title",
                        children: "3. Select Model"
                    }, void 0, false, {
                        fileName: "[project]/frontend/components/SidePanel.jsx",
                        lineNumber: 206,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("select", {
                        className: "sp-select",
                        value: selectedModel?.name || '',
                        onChange: (e)=>handleSelectModel(e.target.value),
                        disabled: loadingModels || isTraining,
                        children: [
                            models.length === 0 && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("option", {
                                value: "",
                                children: "No models"
                            }, void 0, false, {
                                fileName: "[project]/frontend/components/SidePanel.jsx",
                                lineNumber: 213,
                                columnNumber: 35
                            }, this),
                            models.map((m)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("option", {
                                    value: m.name,
                                    children: [
                                        m.algorithm.toUpperCase(),
                                        " · ",
                                        m.name
                                    ]
                                }, m.id, true, {
                                    fileName: "[project]/frontend/components/SidePanel.jsx",
                                    lineNumber: 215,
                                    columnNumber: 13
                                }, this))
                        ]
                    }, void 0, true, {
                        fileName: "[project]/frontend/components/SidePanel.jsx",
                        lineNumber: 207,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("button", {
                        className: "sp-button ghost",
                        onClick: refreshModels,
                        disabled: loadingModels,
                        children: loadingModels ? 'Loading…' : 'Refresh models'
                    }, void 0, false, {
                        fileName: "[project]/frontend/components/SidePanel.jsx",
                        lineNumber: 220,
                        columnNumber: 9
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/frontend/components/SidePanel.jsx",
                lineNumber: 205,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                className: "sp-section",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                        className: "sp-title",
                        children: "4. Prediction Service"
                    }, void 0, false, {
                        fileName: "[project]/frontend/components/SidePanel.jsx",
                        lineNumber: 227,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("button", {
                        className: `sp-button ${predictionActive ? 'danger' : 'success'}`,
                        onClick: handleTogglePrediction,
                        disabled: !selectedModel || serviceBusy,
                        children: predictionActive ? 'Stop Prediction' : 'Start Prediction'
                    }, void 0, false, {
                        fileName: "[project]/frontend/components/SidePanel.jsx",
                        lineNumber: 228,
                        columnNumber: 9
                    }, this),
                    !selectedModel && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                        className: "sp-hint",
                        children: "Select a model to enable predictions"
                    }, void 0, false, {
                        fileName: "[project]/frontend/components/SidePanel.jsx",
                        lineNumber: 236,
                        columnNumber: 11
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/frontend/components/SidePanel.jsx",
                lineNumber: 226,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                className: "sp-footer",
                children: [
                    "v1 • ",
                    new Date().getFullYear()
                ]
            }, void 0, true, {
                fileName: "[project]/frontend/components/SidePanel.jsx",
                lineNumber: 240,
                columnNumber: 7
            }, this)
        ]
    }, void 0, true, {
        fileName: "[project]/frontend/components/SidePanel.jsx",
        lineNumber: 153,
        columnNumber: 5
    }, this);
}
}),
"[project]/frontend/components/PredictionCard.jsx [ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>__TURBOPACK__default__export__
]);
var __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__ = __turbopack_context__.i("[externals]/react/jsx-dev-runtime [external] (react/jsx-dev-runtime, cjs)");
var __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__ = __turbopack_context__.i("[externals]/react [external] (react, cjs)");
;
;
const PredictionCard = ({ prediction, timezone = 'UTC', compact = false })=>{
    const [expanded, setExpanded] = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__["useState"])(false);
    if (!prediction) return null;
    const { direction, probability, confidence, expectedChange, modelType, timestamp, tradingPair } = prediction;
    // Format timestamp according to timezone
    const formattedTime = timestamp ? new Date(timestamp).toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
        timeZone: timezone
    }) : 'Unknown';
    const formattedDate = timestamp ? new Date(timestamp).toLocaleDateString([], {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        timeZone: timezone
    }) : 'Unknown';
    // Derive a friendly timezone label
    const timezoneLabel = timezone === 'Asia/Bangkok' ? 'UTC+7' : timezone;
    // Calculate confidence percentage (prefer backend confidence; fallback to probability-derived)
    const confidenceValue = typeof confidence === 'number' ? confidence : typeof probability === 'number' ? Math.min(1, Math.max(0, Math.abs(probability - 0.5) * 2)) : 0;
    const confidencePercent = Math.round(confidenceValue * 100);
    // Determine color scheme based on direction
    const isUp = direction === 'up';
    const directionColor = isUp ? '#00ff88' : '#ff4444';
    const bgColor = isUp ? 'rgba(0, 255, 136, 0.1)' : 'rgba(255, 68, 68, 0.1)';
    const directionSymbol = isUp ? '↗' : '↘';
    const directionText = isUp ? 'UP' : 'DOWN';
    if (compact) {
        // Compact version for history list
        return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
            className: "prediction-card compact",
            style: {
                borderLeft: `4px solid ${directionColor}`,
                backgroundColor: bgColor
            },
            children: [
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                    className: "prediction-header",
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                            className: "prediction-direction",
                            style: {
                                color: directionColor
                            },
                            children: [
                                directionSymbol,
                                " ",
                                directionText
                            ]
                        }, void 0, true, {
                            fileName: "[project]/frontend/components/PredictionCard.jsx",
                            lineNumber: 61,
                            columnNumber: 11
                        }, ("TURBOPACK compile-time value", void 0)),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                            className: "prediction-time",
                            children: formattedTime
                        }, void 0, false, {
                            fileName: "[project]/frontend/components/PredictionCard.jsx",
                            lineNumber: 64,
                            columnNumber: 11
                        }, ("TURBOPACK compile-time value", void 0))
                    ]
                }, void 0, true, {
                    fileName: "[project]/frontend/components/PredictionCard.jsx",
                    lineNumber: 60,
                    columnNumber: 9
                }, ("TURBOPACK compile-time value", void 0)),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                    className: "prediction-details",
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                            className: "prediction-confidence",
                            children: [
                                confidencePercent,
                                "% confidence"
                            ]
                        }, void 0, true, {
                            fileName: "[project]/frontend/components/PredictionCard.jsx",
                            lineNumber: 69,
                            columnNumber: 11
                        }, ("TURBOPACK compile-time value", void 0)),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                            className: "prediction-pair",
                            children: tradingPair
                        }, void 0, false, {
                            fileName: "[project]/frontend/components/PredictionCard.jsx",
                            lineNumber: 72,
                            columnNumber: 11
                        }, ("TURBOPACK compile-time value", void 0))
                    ]
                }, void 0, true, {
                    fileName: "[project]/frontend/components/PredictionCard.jsx",
                    lineNumber: 68,
                    columnNumber: 9
                }, ("TURBOPACK compile-time value", void 0))
            ]
        }, void 0, true, {
            fileName: "[project]/frontend/components/PredictionCard.jsx",
            lineNumber: 53,
            columnNumber: 7
        }, ("TURBOPACK compile-time value", void 0));
    }
    // Full version
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
        className: "prediction-card",
        style: {
            borderColor: directionColor,
            backgroundColor: bgColor
        },
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                className: "prediction-main",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                        className: "prediction-direction-large",
                        style: {
                            color: directionColor
                        },
                        children: [
                            directionSymbol,
                            " ",
                            directionText
                        ]
                    }, void 0, true, {
                        fileName: "[project]/frontend/components/PredictionCard.jsx",
                        lineNumber: 90,
                        columnNumber: 9
                    }, ("TURBOPACK compile-time value", void 0)),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                        className: "prediction-confidence-large",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                                className: "confidence-value",
                                children: [
                                    confidencePercent,
                                    "%"
                                ]
                            }, void 0, true, {
                                fileName: "[project]/frontend/components/PredictionCard.jsx",
                                lineNumber: 94,
                                columnNumber: 11
                            }, ("TURBOPACK compile-time value", void 0)),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                                className: "confidence-label",
                                children: "Confidence"
                            }, void 0, false, {
                                fileName: "[project]/frontend/components/PredictionCard.jsx",
                                lineNumber: 95,
                                columnNumber: 11
                            }, ("TURBOPACK compile-time value", void 0))
                        ]
                    }, void 0, true, {
                        fileName: "[project]/frontend/components/PredictionCard.jsx",
                        lineNumber: 93,
                        columnNumber: 9
                    }, ("TURBOPACK compile-time value", void 0))
                ]
            }, void 0, true, {
                fileName: "[project]/frontend/components/PredictionCard.jsx",
                lineNumber: 89,
                columnNumber: 7
            }, ("TURBOPACK compile-time value", void 0)),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                className: "prediction-meta",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                        className: "prediction-pair-info",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("span", {
                                className: "meta-label",
                                children: "Pair:"
                            }, void 0, false, {
                                fileName: "[project]/frontend/components/PredictionCard.jsx",
                                lineNumber: 101,
                                columnNumber: 11
                            }, ("TURBOPACK compile-time value", void 0)),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("span", {
                                className: "meta-value",
                                children: tradingPair
                            }, void 0, false, {
                                fileName: "[project]/frontend/components/PredictionCard.jsx",
                                lineNumber: 102,
                                columnNumber: 11
                            }, ("TURBOPACK compile-time value", void 0))
                        ]
                    }, void 0, true, {
                        fileName: "[project]/frontend/components/PredictionCard.jsx",
                        lineNumber: 100,
                        columnNumber: 9
                    }, ("TURBOPACK compile-time value", void 0)),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                        className: "prediction-time-info",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("span", {
                                className: "meta-label",
                                children: "Time:"
                            }, void 0, false, {
                                fileName: "[project]/frontend/components/PredictionCard.jsx",
                                lineNumber: 105,
                                columnNumber: 11
                            }, ("TURBOPACK compile-time value", void 0)),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("span", {
                                className: "meta-value",
                                children: formattedTime
                            }, void 0, false, {
                                fileName: "[project]/frontend/components/PredictionCard.jsx",
                                lineNumber: 106,
                                columnNumber: 11
                            }, ("TURBOPACK compile-time value", void 0))
                        ]
                    }, void 0, true, {
                        fileName: "[project]/frontend/components/PredictionCard.jsx",
                        lineNumber: 104,
                        columnNumber: 9
                    }, ("TURBOPACK compile-time value", void 0)),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                        className: "prediction-date-info",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("span", {
                                className: "meta-label",
                                children: "Date:"
                            }, void 0, false, {
                                fileName: "[project]/frontend/components/PredictionCard.jsx",
                                lineNumber: 109,
                                columnNumber: 11
                            }, ("TURBOPACK compile-time value", void 0)),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("span", {
                                className: "meta-value",
                                children: formattedDate
                            }, void 0, false, {
                                fileName: "[project]/frontend/components/PredictionCard.jsx",
                                lineNumber: 110,
                                columnNumber: 11
                            }, ("TURBOPACK compile-time value", void 0))
                        ]
                    }, void 0, true, {
                        fileName: "[project]/frontend/components/PredictionCard.jsx",
                        lineNumber: 108,
                        columnNumber: 9
                    }, ("TURBOPACK compile-time value", void 0))
                ]
            }, void 0, true, {
                fileName: "[project]/frontend/components/PredictionCard.jsx",
                lineNumber: 99,
                columnNumber: 7
            }, ("TURBOPACK compile-time value", void 0)),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("button", {
                className: "prediction-expand-btn",
                onClick: ()=>setExpanded(!expanded),
                children: expanded ? 'Show Less' : 'Show More'
            }, void 0, false, {
                fileName: "[project]/frontend/components/PredictionCard.jsx",
                lineNumber: 114,
                columnNumber: 7
            }, ("TURBOPACK compile-time value", void 0)),
            expanded && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                className: "prediction-expanded",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                        className: "expanded-row",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("span", {
                                className: "expanded-label",
                                children: "Expected Change:"
                            }, void 0, false, {
                                fileName: "[project]/frontend/components/PredictionCard.jsx",
                                lineNumber: 124,
                                columnNumber: 13
                            }, ("TURBOPACK compile-time value", void 0)),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("span", {
                                className: "expanded-value",
                                style: {
                                    color: directionColor
                                },
                                children: [
                                    expectedChange > 0 ? '+' : '',
                                    (expectedChange * 100).toFixed(2),
                                    "%"
                                ]
                            }, void 0, true, {
                                fileName: "[project]/frontend/components/PredictionCard.jsx",
                                lineNumber: 125,
                                columnNumber: 13
                            }, ("TURBOPACK compile-time value", void 0))
                        ]
                    }, void 0, true, {
                        fileName: "[project]/frontend/components/PredictionCard.jsx",
                        lineNumber: 123,
                        columnNumber: 11
                    }, ("TURBOPACK compile-time value", void 0)),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                        className: "expanded-row",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("span", {
                                className: "expanded-label",
                                children: "Model:"
                            }, void 0, false, {
                                fileName: "[project]/frontend/components/PredictionCard.jsx",
                                lineNumber: 130,
                                columnNumber: 13
                            }, ("TURBOPACK compile-time value", void 0)),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("span", {
                                className: "expanded-value",
                                children: modelType || 'Unknown'
                            }, void 0, false, {
                                fileName: "[project]/frontend/components/PredictionCard.jsx",
                                lineNumber: 131,
                                columnNumber: 13
                            }, ("TURBOPACK compile-time value", void 0))
                        ]
                    }, void 0, true, {
                        fileName: "[project]/frontend/components/PredictionCard.jsx",
                        lineNumber: 129,
                        columnNumber: 11
                    }, ("TURBOPACK compile-time value", void 0)),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                        className: "expanded-row",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("span", {
                                className: "expanded-label",
                                children: "Timezone:"
                            }, void 0, false, {
                                fileName: "[project]/frontend/components/PredictionCard.jsx",
                                lineNumber: 134,
                                columnNumber: 13
                            }, ("TURBOPACK compile-time value", void 0)),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("span", {
                                className: "expanded-value",
                                children: timezoneLabel
                            }, void 0, false, {
                                fileName: "[project]/frontend/components/PredictionCard.jsx",
                                lineNumber: 135,
                                columnNumber: 13
                            }, ("TURBOPACK compile-time value", void 0))
                        ]
                    }, void 0, true, {
                        fileName: "[project]/frontend/components/PredictionCard.jsx",
                        lineNumber: 133,
                        columnNumber: 11
                    }, ("TURBOPACK compile-time value", void 0))
                ]
            }, void 0, true, {
                fileName: "[project]/frontend/components/PredictionCard.jsx",
                lineNumber: 122,
                columnNumber: 9
            }, ("TURBOPACK compile-time value", void 0))
        ]
    }, void 0, true, {
        fileName: "[project]/frontend/components/PredictionCard.jsx",
        lineNumber: 82,
        columnNumber: 5
    }, ("TURBOPACK compile-time value", void 0));
};
const __TURBOPACK__default__export__ = PredictionCard;
}),
"[project]/frontend/components/ConnectionStatus.jsx [ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>__TURBOPACK__default__export__
]);
var __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__ = __turbopack_context__.i("[externals]/react/jsx-dev-runtime [external] (react/jsx-dev-runtime, cjs)");
;
const ConnectionStatus = ({ wsConnected, backendStatus })=>{
    const getStatusInfo = ()=>{
        if (backendStatus === 'error') {
            return {
                icon: '🔴',
                text: 'Backend Offline',
                className: 'status-disconnected'
            };
        }
        if (!wsConnected) {
            return {
                icon: '🟡',
                text: 'Connecting...',
                className: 'status-warning'
            };
        }
        return {
            icon: '🟢',
            text: 'Live Data',
            className: 'status-connected'
        };
    };
    const status = getStatusInfo();
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
        className: `status-indicator ${status.className}`,
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("span", {
                children: status.icon
            }, void 0, false, {
                fileName: "[project]/frontend/components/ConnectionStatus.jsx",
                lineNumber: 30,
                columnNumber: 7
            }, ("TURBOPACK compile-time value", void 0)),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("span", {
                style: {
                    fontSize: '12px',
                    fontWeight: '500'
                },
                children: status.text
            }, void 0, false, {
                fileName: "[project]/frontend/components/ConnectionStatus.jsx",
                lineNumber: 31,
                columnNumber: 7
            }, ("TURBOPACK compile-time value", void 0))
        ]
    }, void 0, true, {
        fileName: "[project]/frontend/components/ConnectionStatus.jsx",
        lineNumber: 29,
        columnNumber: 5
    }, ("TURBOPACK compile-time value", void 0));
};
const __TURBOPACK__default__export__ = ConnectionStatus;
}),
"[project]/frontend/components/CandlestickChart.jsx [ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {

__turbopack_context__.s([
    "default",
    ()=>CandlestickChart
]);
var __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__ = __turbopack_context__.i("[externals]/react/jsx-dev-runtime [external] (react/jsx-dev-runtime, cjs)");
var __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__ = __turbopack_context__.i("[externals]/react [external] (react, cjs)");
var __TURBOPACK__imported__module__$5b$externals$5d2f$lightweight$2d$charts__$5b$external$5d$__$28$lightweight$2d$charts$2c$__esm_import$2c$__$5b$project$5d2f$node_modules$2f$lightweight$2d$charts$29$__ = __turbopack_context__.i("[externals]/lightweight-charts [external] (lightweight-charts, esm_import, [project]/node_modules/lightweight-charts)");
var __TURBOPACK__imported__module__$5b$project$5d2f$frontend$2f$services$2f$api$2e$js__$5b$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/frontend/services/api.js [ssr] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$externals$5d2f$lightweight$2d$charts__$5b$external$5d$__$28$lightweight$2d$charts$2c$__esm_import$2c$__$5b$project$5d2f$node_modules$2f$lightweight$2d$charts$29$__
]);
[__TURBOPACK__imported__module__$5b$externals$5d2f$lightweight$2d$charts__$5b$external$5d$__$28$lightweight$2d$charts$2c$__esm_import$2c$__$5b$project$5d2f$node_modules$2f$lightweight$2d$charts$29$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
;
;
;
;
function CandlestickChart({ tradingPair, prediction }) {
    const containerRef = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__["useRef"])(null);
    const chartRef = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__["useRef"])(null);
    const seriesRef = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__["useRef"])(null);
    const wsRef = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__["useRef"])(null);
    // Initialize chart
    (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__["useEffect"])(()=>{
        if (!containerRef.current) return;
        const chart = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$lightweight$2d$charts__$5b$external$5d$__$28$lightweight$2d$charts$2c$__esm_import$2c$__$5b$project$5d2f$node_modules$2f$lightweight$2d$charts$29$__["createChart"])(containerRef.current, {
            layout: {
                background: {
                    color: '#141414'
                },
                textColor: '#b3b3b3'
            },
            grid: {
                vertLines: {
                    color: '#2a2a2a'
                },
                horzLines: {
                    color: '#2a2a2a'
                }
            },
            crosshair: {
                mode: 0
            },
            rightPriceScale: {
                borderColor: '#2a2a2a'
            },
            timeScale: {
                borderColor: '#2a2a2a',
                timeVisible: true,
                secondsVisible: false
            }
        });
        const candleSeries = chart.addCandlestickSeries({
            upColor: '#00ff88',
            downColor: '#ff4444',
            borderUpColor: '#00ff88',
            borderDownColor: '#ff4444',
            wickUpColor: '#00ff88',
            wickDownColor: '#ff4444'
        });
        chartRef.current = chart;
        seriesRef.current = candleSeries;
        // Resize observer
        const ro = new ResizeObserver((entries)=>{
            for (const entry of entries){
                const { width, height } = entry.contentRect;
                chart.applyOptions({
                    width,
                    height
                });
            }
        });
        ro.observe(containerRef.current);
        return ()=>{
            ro.disconnect();
            chart.remove();
            chartRef.current = null;
            seriesRef.current = null;
        };
    }, []);
    // Fetch historical candles when tradingPair changes
    (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__["useEffect"])(()=>{
        if (!seriesRef.current || !tradingPair) return;
        let cancelled = false;
        const load = async ()=>{
            try {
                const data = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$frontend$2f$services$2f$api$2e$js__$5b$ssr$5d$__$28$ecmascript$29$__["fetchLatestCandles"])({
                    trading_pair: tradingPair,
                    limit: 100
                });
                if (cancelled) return;
                const candles = (data.candles || []).map((c)=>({
                        time: toUnixSeconds(c.timestamp),
                        open: c.open,
                        high: c.high,
                        low: c.low,
                        close: c.close
                    }));
                // Sort ascending by time (lightweight-charts requires this)
                candles.sort((a, b)=>a.time - b.time);
                if (candles.length > 0) {
                    seriesRef.current.setData(candles);
                    chartRef.current?.timeScale().fitContent();
                }
            } catch (err) {
                console.error('Failed to load candles:', err);
            }
        };
        load();
        return ()=>{
            cancelled = true;
        };
    }, [
        tradingPair
    ]);
    // Subscribe to real-time candle updates
    (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__["useEffect"])(()=>{
        if (!seriesRef.current || !tradingPair) return;
        let ws;
        try {
            ws = (0, __TURBOPACK__imported__module__$5b$project$5d2f$frontend$2f$services$2f$api$2e$js__$5b$ssr$5d$__$28$ecmascript$29$__["createMarketDataWebSocket"])();
            ws.onopen = ()=>{
                ws.send(JSON.stringify({
                    action: 'subscribe',
                    trading_pair: tradingPair
                }));
            };
            ws.onmessage = (event)=>{
                try {
                    const msg = JSON.parse(event.data);
                    if (msg.type === 'candle_data' && msg.trading_pair === tradingPair) {
                        const bar = {
                            time: toUnixSeconds(msg.timestamp),
                            open: msg.open,
                            high: msg.high,
                            low: msg.low,
                            close: msg.close
                        };
                        seriesRef.current?.update(bar);
                    }
                } catch (e) {
                // ignore parse errors
                }
            };
            ws.onclose = ()=>{};
            ws.onerror = ()=>{};
            wsRef.current = ws;
        } catch (err) {
            console.error('Market data WS failed:', err);
        }
        return ()=>{
            if (wsRef.current) {
                wsRef.current.close();
                wsRef.current = null;
            }
        };
    }, [
        tradingPair
    ]);
    // Add prediction marker when a new prediction arrives
    (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__["useEffect"])(()=>{
        if (!seriesRef.current || !prediction) return;
        try {
            const ts = prediction.timestamp ? toUnixSeconds(prediction.timestamp instanceof Date ? prediction.timestamp.toISOString() : prediction.timestamp) : Math.floor(Date.now() / 1000);
            const isUp = (prediction.direction || '').toLowerCase() === 'up';
            seriesRef.current.setMarkers([
                {
                    time: ts,
                    position: isUp ? 'belowBar' : 'aboveBar',
                    color: isUp ? '#00ff88' : '#ff4444',
                    shape: isUp ? 'arrowUp' : 'arrowDown',
                    text: isUp ? 'UP' : 'DOWN'
                }
            ]);
        } catch (e) {
        // Marker placement is optional; don't crash
        }
    }, [
        prediction
    ]);
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
        className: "chart-panel",
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                className: "chart-panel-header",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("span", {
                        className: "chart-pair-label",
                        children: tradingPair || 'No pair selected'
                    }, void 0, false, {
                        fileName: "[project]/frontend/components/CandlestickChart.jsx",
                        lineNumber: 175,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("span", {
                        className: "chart-timeframe",
                        children: "1m"
                    }, void 0, false, {
                        fileName: "[project]/frontend/components/CandlestickChart.jsx",
                        lineNumber: 176,
                        columnNumber: 9
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/frontend/components/CandlestickChart.jsx",
                lineNumber: 174,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                className: "chart-wrapper",
                ref: containerRef
            }, void 0, false, {
                fileName: "[project]/frontend/components/CandlestickChart.jsx",
                lineNumber: 178,
                columnNumber: 7
            }, this)
        ]
    }, void 0, true, {
        fileName: "[project]/frontend/components/CandlestickChart.jsx",
        lineNumber: 173,
        columnNumber: 5
    }, this);
}
/** Convert an ISO timestamp string or Date to Unix seconds (UTC) */ function toUnixSeconds(ts) {
    if (!ts) return Math.floor(Date.now() / 1000);
    const d = typeof ts === 'string' ? new Date(ts) : ts;
    return Math.floor(d.getTime() / 1000);
}
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[project]/frontend/components/ServiceStatusBar.jsx [ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>__TURBOPACK__default__export__
]);
var __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__ = __turbopack_context__.i("[externals]/react/jsx-dev-runtime [external] (react/jsx-dev-runtime, cjs)");
var __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__ = __turbopack_context__.i("[externals]/react [external] (react, cjs)");
var __TURBOPACK__imported__module__$5b$project$5d2f$frontend$2f$services$2f$api$2e$js__$5b$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/frontend/services/api.js [ssr] (ecmascript)");
;
;
;
const SERVICE_LABELS = {
    data_collection: 'Data Collection',
    ml_training: 'ML Training',
    prediction: 'Prediction'
};
// Services that run on-demand (show gray when stopped, no alarm)
const ON_DEMAND_SERVICES = new Set([
    'ml_training',
    'prediction'
]);
const ServiceStatusBar = ()=>{
    const [statuses, setStatuses] = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__["useState"])({});
    const intervalRef = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__["useRef"])(null);
    const fetchStatuses = async ()=>{
        try {
            const services = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$frontend$2f$services$2f$api$2e$js__$5b$ssr$5d$__$28$ecmascript$29$__["getServiceStatuses"])();
            setStatuses(services || {});
        } catch  {
            // If the gateway itself is unreachable, mark everything unknown
            setStatuses({});
        }
    };
    (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__["useEffect"])(()=>{
        fetchStatuses();
        intervalRef.current = setInterval(fetchStatuses, 15000);
        return ()=>clearInterval(intervalRef.current);
    }, []);
    const getDotClass = (serviceKey)=>{
        const status = statuses[serviceKey];
        if (!status || status === 'unknown') return 'status-dot gray';
        if (status === 'healthy') return 'status-dot green';
        // On-demand services show gray when unhealthy (just stopped), not red
        if (ON_DEMAND_SERVICES.has(serviceKey)) return 'status-dot gray';
        return 'status-dot red';
    };
    const getLabel = (serviceKey)=>{
        const status = statuses[serviceKey];
        if (!status || status === 'unknown') return 'Unknown';
        if (status === 'healthy') return 'Healthy';
        if (ON_DEMAND_SERVICES.has(serviceKey)) return 'Stopped';
        return 'Unhealthy';
    };
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
        className: "service-status-bar",
        children: [
            Object.keys(SERVICE_LABELS).map((key)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                    className: "service-indicator",
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("span", {
                            className: getDotClass(key)
                        }, void 0, false, {
                            fileName: "[project]/frontend/components/ServiceStatusBar.jsx",
                            lineNumber: 54,
                            columnNumber: 11
                        }, ("TURBOPACK compile-time value", void 0)),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("span", {
                            className: "service-label",
                            children: SERVICE_LABELS[key]
                        }, void 0, false, {
                            fileName: "[project]/frontend/components/ServiceStatusBar.jsx",
                            lineNumber: 55,
                            columnNumber: 11
                        }, ("TURBOPACK compile-time value", void 0)),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("span", {
                            className: "service-state",
                            children: getLabel(key)
                        }, void 0, false, {
                            fileName: "[project]/frontend/components/ServiceStatusBar.jsx",
                            lineNumber: 56,
                            columnNumber: 11
                        }, ("TURBOPACK compile-time value", void 0))
                    ]
                }, key, true, {
                    fileName: "[project]/frontend/components/ServiceStatusBar.jsx",
                    lineNumber: 53,
                    columnNumber: 9
                }, ("TURBOPACK compile-time value", void 0))),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                className: "service-indicator",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("span", {
                        className: `status-dot ${Object.keys(statuses).length > 0 ? 'green' : 'red'}`
                    }, void 0, false, {
                        fileName: "[project]/frontend/components/ServiceStatusBar.jsx",
                        lineNumber: 61,
                        columnNumber: 9
                    }, ("TURBOPACK compile-time value", void 0)),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("span", {
                        className: "service-label",
                        children: "API Gateway"
                    }, void 0, false, {
                        fileName: "[project]/frontend/components/ServiceStatusBar.jsx",
                        lineNumber: 62,
                        columnNumber: 9
                    }, ("TURBOPACK compile-time value", void 0)),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("span", {
                        className: "service-state",
                        children: Object.keys(statuses).length > 0 ? 'Healthy' : 'Unreachable'
                    }, void 0, false, {
                        fileName: "[project]/frontend/components/ServiceStatusBar.jsx",
                        lineNumber: 63,
                        columnNumber: 9
                    }, ("TURBOPACK compile-time value", void 0))
                ]
            }, void 0, true, {
                fileName: "[project]/frontend/components/ServiceStatusBar.jsx",
                lineNumber: 60,
                columnNumber: 7
            }, ("TURBOPACK compile-time value", void 0))
        ]
    }, void 0, true, {
        fileName: "[project]/frontend/components/ServiceStatusBar.jsx",
        lineNumber: 51,
        columnNumber: 5
    }, ("TURBOPACK compile-time value", void 0));
};
const __TURBOPACK__default__export__ = ServiceStatusBar;
}),
"[project]/frontend/components/AccuracyTracker.jsx [ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>__TURBOPACK__default__export__
]);
var __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__ = __turbopack_context__.i("[externals]/react/jsx-dev-runtime [external] (react/jsx-dev-runtime, cjs)");
var __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__ = __turbopack_context__.i("[externals]/react [external] (react, cjs)");
var __TURBOPACK__imported__module__$5b$project$5d2f$frontend$2f$services$2f$api$2e$js__$5b$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/frontend/services/api.js [ssr] (ecmascript)");
;
;
;
const AccuracyTracker = ()=>{
    const [accuracy, setAccuracy] = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__["useState"])(null);
    const [error, setError] = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__["useState"])(false);
    const intervalRef = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__["useRef"])(null);
    const fetchAccuracy = async ()=>{
        try {
            const data = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$frontend$2f$services$2f$api$2e$js__$5b$ssr$5d$__$28$ecmascript$29$__["getPredictionAccuracy"])();
            setAccuracy(data);
            setError(false);
        } catch  {
            setError(true);
        }
    };
    (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__["useEffect"])(()=>{
        fetchAccuracy();
        intervalRef.current = setInterval(fetchAccuracy, 30000);
        return ()=>clearInterval(intervalRef.current);
    }, []);
    if (error || !accuracy) {
        return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
            className: "accuracy-tracker",
            children: [
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("h3", {
                    children: "Prediction Accuracy"
                }, void 0, false, {
                    fileName: "[project]/frontend/components/AccuracyTracker.jsx",
                    lineNumber: 28,
                    columnNumber: 9
                }, ("TURBOPACK compile-time value", void 0)),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("p", {
                    className: "accuracy-unavailable",
                    children: error ? 'Prediction service unavailable' : 'Loading...'
                }, void 0, false, {
                    fileName: "[project]/frontend/components/AccuracyTracker.jsx",
                    lineNumber: 29,
                    columnNumber: 9
                }, ("TURBOPACK compile-time value", void 0))
            ]
        }, void 0, true, {
            fileName: "[project]/frontend/components/AccuracyTracker.jsx",
            lineNumber: 27,
            columnNumber: 7
        }, ("TURBOPACK compile-time value", void 0));
    }
    if (accuracy.total_predictions === 0) {
        return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
            className: "accuracy-tracker",
            children: [
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("h3", {
                    children: "Prediction Accuracy"
                }, void 0, false, {
                    fileName: "[project]/frontend/components/AccuracyTracker.jsx",
                    lineNumber: 39,
                    columnNumber: 9
                }, ("TURBOPACK compile-time value", void 0)),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("p", {
                    className: "accuracy-unavailable",
                    children: "No predictions recorded yet"
                }, void 0, false, {
                    fileName: "[project]/frontend/components/AccuracyTracker.jsx",
                    lineNumber: 40,
                    columnNumber: 9
                }, ("TURBOPACK compile-time value", void 0))
            ]
        }, void 0, true, {
            fileName: "[project]/frontend/components/AccuracyTracker.jsx",
            lineNumber: 38,
            columnNumber: 7
        }, ("TURBOPACK compile-time value", void 0));
    }
    const pct = (val)=>`${(val * 100).toFixed(1)}%`;
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
        className: "accuracy-tracker",
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("h3", {
                children: "Prediction Accuracy"
            }, void 0, false, {
                fileName: "[project]/frontend/components/AccuracyTracker.jsx",
                lineNumber: 49,
                columnNumber: 7
            }, ("TURBOPACK compile-time value", void 0)),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                className: "accuracy-hero",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("span", {
                        className: "accuracy-big-number",
                        children: pct(accuracy.win_rate)
                    }, void 0, false, {
                        fileName: "[project]/frontend/components/AccuracyTracker.jsx",
                        lineNumber: 52,
                        columnNumber: 9
                    }, ("TURBOPACK compile-time value", void 0)),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("span", {
                        className: "accuracy-big-label",
                        children: "Win Rate"
                    }, void 0, false, {
                        fileName: "[project]/frontend/components/AccuracyTracker.jsx",
                        lineNumber: 53,
                        columnNumber: 9
                    }, ("TURBOPACK compile-time value", void 0))
                ]
            }, void 0, true, {
                fileName: "[project]/frontend/components/AccuracyTracker.jsx",
                lineNumber: 51,
                columnNumber: 7
            }, ("TURBOPACK compile-time value", void 0)),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                className: "accuracy-stats-grid",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                        className: "accuracy-stat",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("span", {
                                className: "stat-value",
                                children: pct(accuracy.recent_accuracy_24h)
                            }, void 0, false, {
                                fileName: "[project]/frontend/components/AccuracyTracker.jsx",
                                lineNumber: 58,
                                columnNumber: 11
                            }, ("TURBOPACK compile-time value", void 0)),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("span", {
                                className: "stat-label",
                                children: "24h"
                            }, void 0, false, {
                                fileName: "[project]/frontend/components/AccuracyTracker.jsx",
                                lineNumber: 59,
                                columnNumber: 11
                            }, ("TURBOPACK compile-time value", void 0))
                        ]
                    }, void 0, true, {
                        fileName: "[project]/frontend/components/AccuracyTracker.jsx",
                        lineNumber: 57,
                        columnNumber: 9
                    }, ("TURBOPACK compile-time value", void 0)),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                        className: "accuracy-stat",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("span", {
                                className: "stat-value",
                                children: pct(accuracy.recent_accuracy_7d)
                            }, void 0, false, {
                                fileName: "[project]/frontend/components/AccuracyTracker.jsx",
                                lineNumber: 62,
                                columnNumber: 11
                            }, ("TURBOPACK compile-time value", void 0)),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("span", {
                                className: "stat-label",
                                children: "7d"
                            }, void 0, false, {
                                fileName: "[project]/frontend/components/AccuracyTracker.jsx",
                                lineNumber: 63,
                                columnNumber: 11
                            }, ("TURBOPACK compile-time value", void 0))
                        ]
                    }, void 0, true, {
                        fileName: "[project]/frontend/components/AccuracyTracker.jsx",
                        lineNumber: 61,
                        columnNumber: 9
                    }, ("TURBOPACK compile-time value", void 0)),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                        className: "accuracy-stat",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("span", {
                                className: "stat-value",
                                children: accuracy.total_predictions
                            }, void 0, false, {
                                fileName: "[project]/frontend/components/AccuracyTracker.jsx",
                                lineNumber: 66,
                                columnNumber: 11
                            }, ("TURBOPACK compile-time value", void 0)),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("span", {
                                className: "stat-label",
                                children: "Total"
                            }, void 0, false, {
                                fileName: "[project]/frontend/components/AccuracyTracker.jsx",
                                lineNumber: 67,
                                columnNumber: 11
                            }, ("TURBOPACK compile-time value", void 0))
                        ]
                    }, void 0, true, {
                        fileName: "[project]/frontend/components/AccuracyTracker.jsx",
                        lineNumber: 65,
                        columnNumber: 9
                    }, ("TURBOPACK compile-time value", void 0)),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                        className: "accuracy-stat",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("span", {
                                className: "stat-value",
                                children: accuracy.correct_predictions
                            }, void 0, false, {
                                fileName: "[project]/frontend/components/AccuracyTracker.jsx",
                                lineNumber: 70,
                                columnNumber: 11
                            }, ("TURBOPACK compile-time value", void 0)),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("span", {
                                className: "stat-label",
                                children: "Correct"
                            }, void 0, false, {
                                fileName: "[project]/frontend/components/AccuracyTracker.jsx",
                                lineNumber: 71,
                                columnNumber: 11
                            }, ("TURBOPACK compile-time value", void 0))
                        ]
                    }, void 0, true, {
                        fileName: "[project]/frontend/components/AccuracyTracker.jsx",
                        lineNumber: 69,
                        columnNumber: 9
                    }, ("TURBOPACK compile-time value", void 0))
                ]
            }, void 0, true, {
                fileName: "[project]/frontend/components/AccuracyTracker.jsx",
                lineNumber: 56,
                columnNumber: 7
            }, ("TURBOPACK compile-time value", void 0)),
            accuracy.by_model && Object.keys(accuracy.by_model).length > 0 && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                className: "accuracy-models",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("h4", {
                        children: "Per Model"
                    }, void 0, false, {
                        fileName: "[project]/frontend/components/AccuracyTracker.jsx",
                        lineNumber: 77,
                        columnNumber: 11
                    }, ("TURBOPACK compile-time value", void 0)),
                    Object.entries(accuracy.by_model).map(([model, stats])=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                            className: "accuracy-model-row",
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("span", {
                                    className: "model-name",
                                    children: model
                                }, void 0, false, {
                                    fileName: "[project]/frontend/components/AccuracyTracker.jsx",
                                    lineNumber: 80,
                                    columnNumber: 15
                                }, ("TURBOPACK compile-time value", void 0)),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("span", {
                                    className: "model-accuracy",
                                    children: pct(stats.accuracy)
                                }, void 0, false, {
                                    fileName: "[project]/frontend/components/AccuracyTracker.jsx",
                                    lineNumber: 81,
                                    columnNumber: 15
                                }, ("TURBOPACK compile-time value", void 0)),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("span", {
                                    className: "model-count",
                                    children: [
                                        stats.correct,
                                        "/",
                                        stats.total
                                    ]
                                }, void 0, true, {
                                    fileName: "[project]/frontend/components/AccuracyTracker.jsx",
                                    lineNumber: 82,
                                    columnNumber: 15
                                }, ("TURBOPACK compile-time value", void 0))
                            ]
                        }, model, true, {
                            fileName: "[project]/frontend/components/AccuracyTracker.jsx",
                            lineNumber: 79,
                            columnNumber: 13
                        }, ("TURBOPACK compile-time value", void 0)))
                ]
            }, void 0, true, {
                fileName: "[project]/frontend/components/AccuracyTracker.jsx",
                lineNumber: 76,
                columnNumber: 9
            }, ("TURBOPACK compile-time value", void 0))
        ]
    }, void 0, true, {
        fileName: "[project]/frontend/components/AccuracyTracker.jsx",
        lineNumber: 48,
        columnNumber: 5
    }, ("TURBOPACK compile-time value", void 0));
};
const __TURBOPACK__default__export__ = AccuracyTracker;
}),
"[project]/frontend/components/PredictionDashboard.jsx [ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {

__turbopack_context__.s([
    "default",
    ()=>__TURBOPACK__default__export__
]);
var __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__ = __turbopack_context__.i("[externals]/react/jsx-dev-runtime [external] (react/jsx-dev-runtime, cjs)");
var __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__ = __turbopack_context__.i("[externals]/react [external] (react, cjs)");
var __TURBOPACK__imported__module__$5b$project$5d2f$frontend$2f$components$2f$SidePanel$2e$jsx__$5b$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/frontend/components/SidePanel.jsx [ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$frontend$2f$components$2f$PredictionCard$2e$jsx__$5b$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/frontend/components/PredictionCard.jsx [ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$frontend$2f$components$2f$ConnectionStatus$2e$jsx__$5b$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/frontend/components/ConnectionStatus.jsx [ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$frontend$2f$components$2f$CandlestickChart$2e$jsx__$5b$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/frontend/components/CandlestickChart.jsx [ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$frontend$2f$components$2f$ServiceStatusBar$2e$jsx__$5b$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/frontend/components/ServiceStatusBar.jsx [ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$frontend$2f$components$2f$AccuracyTracker$2e$jsx__$5b$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/frontend/components/AccuracyTracker.jsx [ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$frontend$2f$services$2f$api$2e$js__$5b$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/frontend/services/api.js [ssr] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$project$5d2f$frontend$2f$components$2f$CandlestickChart$2e$jsx__$5b$ssr$5d$__$28$ecmascript$29$__
]);
[__TURBOPACK__imported__module__$5b$project$5d2f$frontend$2f$components$2f$CandlestickChart$2e$jsx__$5b$ssr$5d$__$28$ecmascript$29$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
;
;
;
;
;
;
;
;
;
const PredictionDashboard = ()=>{
    // Configuration state
    const [selectedPair, setSelectedPair] = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__["useState"])('USD/BRL(OTC)');
    const [timezone, setTimezone] = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__["useState"])('Asia/Bangkok');
    const [predictionActive, setPredictionActive] = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__["useState"])(false);
    // Model selection state (managed by SidePanel as single source of truth)
    const [selectedModel, setSelectedModel] = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__["useState"])(null);
    // Prediction state
    const [prediction, setPrediction] = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__["useState"])(null);
    const [predictionHistory, setPredictionHistory] = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__["useState"])([]);
    // Connection state
    const [backendStatus, setBackendStatus] = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__["useState"])('checking');
    const [wsConnected, setWsConnected] = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__["useState"])(false);
    const wsRef = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__["useRef"])(null);
    // System status
    const [systemStatus, setSystemStatus] = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__["useState"])({});
    // (Timezone remains configurable internally; UI control migrated out for now)
    // Helper: parse backend timestamps as UTC if missing TZ info
    const parseUtc = (ts)=>{
        if (!ts) return null;
        if (ts instanceof Date) return ts; // already a Date
        if (/(Z|[\+\-]\d{2}:?\d{2})$/.test(ts)) return new Date(ts);
        return new Date(ts + 'Z');
    };
    // Initialize on component mount
    (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__["useEffect"])(()=>{
        checkBackendStatus();
        return ()=>{
            if (wsRef.current) {
                wsRef.current.close();
            }
        };
    }, []);
    // Connect WebSocket when prediction is activated
    (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__["useEffect"])(()=>{
        if (predictionActive) {
            connectWebSocket();
            (0, __TURBOPACK__imported__module__$5b$project$5d2f$frontend$2f$services$2f$api$2e$js__$5b$ssr$5d$__$28$ecmascript$29$__["startPredictionService"])().catch((error)=>{
                console.error('Failed to start prediction service:', error);
            });
        } else {
            if (wsRef.current) {
                wsRef.current.close();
                setWsConnected(false);
            }
            (0, __TURBOPACK__imported__module__$5b$project$5d2f$frontend$2f$services$2f$api$2e$js__$5b$ssr$5d$__$28$ecmascript$29$__["stopPredictionService"])().catch((error)=>{
                console.error('Failed to stop prediction service:', error);
            });
        }
    }, [
        predictionActive
    ]);
    // Subscribe to new pair when it changes
    (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__["useEffect"])(()=>{
        if (wsConnected && wsRef.current && predictionActive) {
            subscribeToPredictions();
        }
    }, [
        selectedPair,
        wsConnected
    ]);
    const checkBackendStatus = async ()=>{
        try {
            const data = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$frontend$2f$services$2f$api$2e$js__$5b$ssr$5d$__$28$ecmascript$29$__["getHealthStatus"])();
            setBackendStatus(data.status === 'healthy' || data.status === 'degraded' ? 'connected' : 'error');
        } catch (error) {
            console.error('Backend health check failed:', error);
            setBackendStatus('error');
        }
    };
    const connectWebSocket = ()=>{
        try {
            // Use the API service to create WebSocket
            const ws = (0, __TURBOPACK__imported__module__$5b$project$5d2f$frontend$2f$services$2f$api$2e$js__$5b$ssr$5d$__$28$ecmascript$29$__["createPredictionWebSocket"])();
            ws.onopen = ()=>{
                console.log('🔌 ML WebSocket connected');
                setWsConnected(true);
                subscribeToPredictions();
            };
            ws.onmessage = (event)=>{
                try {
                    const data = JSON.parse(event.data);
                    console.log('🤖 ML WebSocket message:', data);
                    if (data.type === 'prediction' && data.trading_pair === selectedPair) {
                        // Add a timestamp to ensure we're getting fresh data
                        const predictionData = {
                            direction: (data.prediction || '').toLowerCase(),
                            probability: data.probability,
                            confidence: data.confidence,
                            expectedChange: data.expected_change,
                            modelType: data.model_used,
                            timestamp: parseUtc(data.timestamp || new Date().toISOString()),
                            tradingPair: data.trading_pair,
                            _receivedAt: new Date().getTime() // Add client-side timestamp for freshness tracking
                        };
                        console.log('🤖 ML Prediction received:', predictionData);
                        setPrediction(predictionData);
                        // Add to history
                        setPredictionHistory((prev)=>{
                            const newHistory = [
                                predictionData,
                                ...prev
                            ];
                            // Keep only last 20 predictions
                            return newHistory.slice(0, 20);
                        });
                    }
                } catch (error) {
                    console.error('Error parsing WebSocket message:', error);
                }
            };
            ws.onclose = ()=>{
                console.log('ML WebSocket disconnected');
                setWsConnected(false);
                // Only reconnect if prediction is still active
                if (predictionActive) {
                    setTimeout(connectWebSocket, 3000);
                }
            };
            ws.onerror = (error)=>{
                console.error('ML WebSocket error:', error);
                setWsConnected(false);
            };
            wsRef.current = ws;
        } catch (error) {
            console.error('ML WebSocket connection failed:', error);
            setWsConnected(false);
        }
    };
    const subscribeToPredictions = ()=>{
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            const subscribeMsg = {
                action: 'subscribe',
                trading_pair: selectedPair,
                // Include selected model information if available
                model_name: selectedModel?.name,
                model_type: selectedModel?.algorithm
            };
            wsRef.current.send(JSON.stringify(subscribeMsg));
            console.log(`🔔 Subscribed to predictions for ${selectedPair} using model ${selectedModel?.name || 'default'}`);
        } else {
            console.warn('WebSocket not connected, cannot subscribe');
        }
    };
    const fetchLatestPrediction = async ()=>{
        try {
            // Pass selected model information to get the latest prediction
            const data = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$frontend$2f$services$2f$api$2e$js__$5b$ssr$5d$__$28$ecmascript$29$__["getLatestPrediction"])(selectedPair, selectedModel?.algorithm, selectedModel?.name);
            if (!data || !data.prediction) {
                console.log('No prediction available yet');
                return;
            }
            console.log('📊 Latest prediction:', data);
            // Format the prediction data
            const predictionData = {
                direction: (data.prediction || '').toLowerCase(),
                probability: data.probability,
                confidence: data.confidence,
                expectedChange: data.expected_change,
                modelType: data.model_used,
                timestamp: parseUtc(data.timestamp),
                tradingPair: selectedPair
            };
            // Always update the prediction with the latest data
            setPrediction(predictionData);
            // Add to history if it's different from the previous one
            setPredictionHistory((prev)=>{
                // Check if we already have this exact prediction (avoid duplicates)
                if (prev.length > 0 && prev[0].direction === predictionData.direction && prev[0].probability === predictionData.probability && prev[0].confidence === predictionData.confidence && prev[0].modelType === predictionData.modelType) {
                    return prev;
                }
                const newHistory = [
                    predictionData,
                    ...prev
                ];
                return newHistory.slice(0, 20); // Keep only last 20 predictions
            });
        } catch (error) {
            console.error('Failed to fetch prediction:', error);
        }
    };
    const handlePairChange = (newPair)=>{
        setSelectedPair(newPair);
        setPrediction(null);
    };
    const handleTimezoneChange = (newTimezone)=>{
        setTimezone(newTimezone);
    };
    // SidePanel will manage start/stop and model selection directly
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
        className: "dashboard-container",
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("header", {
                className: "header",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                        className: "header-title",
                        children: "OTC Predictor - ML Prediction Dashboard"
                    }, void 0, false, {
                        fileName: "[project]/frontend/components/PredictionDashboard.jsx",
                        lineNumber: 238,
                        columnNumber: 9
                    }, ("TURBOPACK compile-time value", void 0)),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                        className: "header-controls",
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$frontend$2f$components$2f$ConnectionStatus$2e$jsx__$5b$ssr$5d$__$28$ecmascript$29$__["default"], {
                            wsConnected: wsConnected,
                            backendStatus: backendStatus
                        }, void 0, false, {
                            fileName: "[project]/frontend/components/PredictionDashboard.jsx",
                            lineNumber: 242,
                            columnNumber: 11
                        }, ("TURBOPACK compile-time value", void 0))
                    }, void 0, false, {
                        fileName: "[project]/frontend/components/PredictionDashboard.jsx",
                        lineNumber: 241,
                        columnNumber: 9
                    }, ("TURBOPACK compile-time value", void 0))
                ]
            }, void 0, true, {
                fileName: "[project]/frontend/components/PredictionDashboard.jsx",
                lineNumber: 237,
                columnNumber: 7
            }, ("TURBOPACK compile-time value", void 0)),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$frontend$2f$components$2f$ServiceStatusBar$2e$jsx__$5b$ssr$5d$__$28$ecmascript$29$__["default"], {}, void 0, false, {
                fileName: "[project]/frontend/components/PredictionDashboard.jsx",
                lineNumber: 250,
                columnNumber: 7
            }, ("TURBOPACK compile-time value", void 0)),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                className: "main-content three-col",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                        className: "config-panel",
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$frontend$2f$components$2f$SidePanel$2e$jsx__$5b$ssr$5d$__$28$ecmascript$29$__["default"], {
                            selectedPair: selectedPair,
                            onPairChange: handlePairChange,
                            selectedModel: selectedModel,
                            onModelChange: setSelectedModel,
                            predictionActive: predictionActive,
                            setPredictionActive: setPredictionActive
                        }, void 0, false, {
                            fileName: "[project]/frontend/components/PredictionDashboard.jsx",
                            lineNumber: 256,
                            columnNumber: 11
                        }, ("TURBOPACK compile-time value", void 0))
                    }, void 0, false, {
                        fileName: "[project]/frontend/components/PredictionDashboard.jsx",
                        lineNumber: 255,
                        columnNumber: 9
                    }, ("TURBOPACK compile-time value", void 0)),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                        className: "chart-center-panel",
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$frontend$2f$components$2f$CandlestickChart$2e$jsx__$5b$ssr$5d$__$28$ecmascript$29$__["default"], {
                            tradingPair: selectedPair,
                            prediction: prediction
                        }, void 0, false, {
                            fileName: "[project]/frontend/components/PredictionDashboard.jsx",
                            lineNumber: 268,
                            columnNumber: 11
                        }, ("TURBOPACK compile-time value", void 0))
                    }, void 0, false, {
                        fileName: "[project]/frontend/components/PredictionDashboard.jsx",
                        lineNumber: 267,
                        columnNumber: 9
                    }, ("TURBOPACK compile-time value", void 0)),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                        className: "prediction-panel",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                                className: "current-prediction",
                                children: [
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("h2", {
                                        children: "Current Prediction"
                                    }, void 0, false, {
                                        fileName: "[project]/frontend/components/PredictionDashboard.jsx",
                                        lineNumber: 278,
                                        columnNumber: 13
                                    }, ("TURBOPACK compile-time value", void 0)),
                                    prediction ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$frontend$2f$components$2f$PredictionCard$2e$jsx__$5b$ssr$5d$__$28$ecmascript$29$__["default"], {
                                        prediction: prediction,
                                        timezone: timezone
                                    }, void 0, false, {
                                        fileName: "[project]/frontend/components/PredictionDashboard.jsx",
                                        lineNumber: 280,
                                        columnNumber: 15
                                    }, ("TURBOPACK compile-time value", void 0)) : /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                                        className: "no-prediction",
                                        children: predictionActive ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                                            className: "loading-prediction",
                                            children: [
                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                                                    className: "spinner"
                                                }, void 0, false, {
                                                    fileName: "[project]/frontend/components/PredictionDashboard.jsx",
                                                    lineNumber: 285,
                                                    columnNumber: 21
                                                }, ("TURBOPACK compile-time value", void 0)),
                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("p", {
                                                    children: "Waiting for prediction..."
                                                }, void 0, false, {
                                                    fileName: "[project]/frontend/components/PredictionDashboard.jsx",
                                                    lineNumber: 286,
                                                    columnNumber: 21
                                                }, ("TURBOPACK compile-time value", void 0))
                                            ]
                                        }, void 0, true, {
                                            fileName: "[project]/frontend/components/PredictionDashboard.jsx",
                                            lineNumber: 284,
                                            columnNumber: 19
                                        }, ("TURBOPACK compile-time value", void 0)) : /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("p", {
                                            children: "Start the prediction service to see results"
                                        }, void 0, false, {
                                            fileName: "[project]/frontend/components/PredictionDashboard.jsx",
                                            lineNumber: 289,
                                            columnNumber: 19
                                        }, ("TURBOPACK compile-time value", void 0))
                                    }, void 0, false, {
                                        fileName: "[project]/frontend/components/PredictionDashboard.jsx",
                                        lineNumber: 282,
                                        columnNumber: 15
                                    }, ("TURBOPACK compile-time value", void 0))
                                ]
                            }, void 0, true, {
                                fileName: "[project]/frontend/components/PredictionDashboard.jsx",
                                lineNumber: 277,
                                columnNumber: 11
                            }, ("TURBOPACK compile-time value", void 0)),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$frontend$2f$components$2f$AccuracyTracker$2e$jsx__$5b$ssr$5d$__$28$ecmascript$29$__["default"], {}, void 0, false, {
                                fileName: "[project]/frontend/components/PredictionDashboard.jsx",
                                lineNumber: 296,
                                columnNumber: 11
                            }, ("TURBOPACK compile-time value", void 0)),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                                className: "prediction-history",
                                children: [
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("h2", {
                                        children: "Prediction History"
                                    }, void 0, false, {
                                        fileName: "[project]/frontend/components/PredictionDashboard.jsx",
                                        lineNumber: 300,
                                        columnNumber: 13
                                    }, ("TURBOPACK compile-time value", void 0)),
                                    predictionHistory.length > 0 ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                                        className: "history-list",
                                        children: predictionHistory.map((pred, index)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                                                className: "history-item",
                                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$frontend$2f$components$2f$PredictionCard$2e$jsx__$5b$ssr$5d$__$28$ecmascript$29$__["default"], {
                                                    prediction: pred,
                                                    timezone: timezone,
                                                    compact: true
                                                }, void 0, false, {
                                                    fileName: "[project]/frontend/components/PredictionDashboard.jsx",
                                                    lineNumber: 305,
                                                    columnNumber: 21
                                                }, ("TURBOPACK compile-time value", void 0))
                                            }, index, false, {
                                                fileName: "[project]/frontend/components/PredictionDashboard.jsx",
                                                lineNumber: 304,
                                                columnNumber: 19
                                            }, ("TURBOPACK compile-time value", void 0)))
                                    }, void 0, false, {
                                        fileName: "[project]/frontend/components/PredictionDashboard.jsx",
                                        lineNumber: 302,
                                        columnNumber: 15
                                    }, ("TURBOPACK compile-time value", void 0)) : /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("p", {
                                        className: "no-history",
                                        children: "No prediction history available"
                                    }, void 0, false, {
                                        fileName: "[project]/frontend/components/PredictionDashboard.jsx",
                                        lineNumber: 314,
                                        columnNumber: 15
                                    }, ("TURBOPACK compile-time value", void 0))
                                ]
                            }, void 0, true, {
                                fileName: "[project]/frontend/components/PredictionDashboard.jsx",
                                lineNumber: 299,
                                columnNumber: 11
                            }, ("TURBOPACK compile-time value", void 0))
                        ]
                    }, void 0, true, {
                        fileName: "[project]/frontend/components/PredictionDashboard.jsx",
                        lineNumber: 275,
                        columnNumber: 9
                    }, ("TURBOPACK compile-time value", void 0))
                ]
            }, void 0, true, {
                fileName: "[project]/frontend/components/PredictionDashboard.jsx",
                lineNumber: 253,
                columnNumber: 7
            }, ("TURBOPACK compile-time value", void 0))
        ]
    }, void 0, true, {
        fileName: "[project]/frontend/components/PredictionDashboard.jsx",
        lineNumber: 235,
        columnNumber: 5
    }, ("TURBOPACK compile-time value", void 0));
};
const __TURBOPACK__default__export__ = PredictionDashboard;
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[project]/frontend/pages/index.jsx [ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {

__turbopack_context__.s([
    "default",
    ()=>Home
]);
var __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__ = __turbopack_context__.i("[externals]/react/jsx-dev-runtime [external] (react/jsx-dev-runtime, cjs)");
var __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__ = __turbopack_context__.i("[externals]/react [external] (react, cjs)");
var __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$head$2e$js__$5b$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/node_modules/next/head.js [ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$frontend$2f$components$2f$PredictionDashboard$2e$jsx__$5b$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/frontend/components/PredictionDashboard.jsx [ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$frontend$2f$services$2f$api$2e$js__$5b$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/frontend/services/api.js [ssr] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$project$5d2f$frontend$2f$components$2f$PredictionDashboard$2e$jsx__$5b$ssr$5d$__$28$ecmascript$29$__
]);
[__TURBOPACK__imported__module__$5b$project$5d2f$frontend$2f$components$2f$PredictionDashboard$2e$jsx__$5b$ssr$5d$__$28$ecmascript$29$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
;
;
;
;
;
const SERVICE_NAMES = {
    api_gateway: 'API Gateway',
    data_collection: 'Data Collection',
    ml_training: 'ML Training',
    prediction: 'Prediction Service'
};
// Only the gateway needs to be up to proceed — others are shown for info
const REQUIRED_SERVICE = 'api_gateway';
function Home() {
    const [ready, setReady] = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__["useState"])(false);
    const [checking, setChecking] = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__["useState"])(true);
    const [retryCount, setRetryCount] = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__["useState"])(0);
    const [errorInfo, setErrorInfo] = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__["useState"])(null);
    const [services, setServices] = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__["useState"])({
        api_gateway: 'checking',
        data_collection: 'checking',
        ml_training: 'checking',
        prediction: 'checking'
    });
    const checkServices = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__["useCallback"])(async ()=>{
        setChecking(true);
        // Mark all as checking
        setServices({
            api_gateway: 'checking',
            data_collection: 'checking',
            ml_training: 'checking',
            prediction: 'checking'
        });
        try {
            const data = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$frontend$2f$services$2f$api$2e$js__$5b$ssr$5d$__$28$ecmascript$29$__["getHealthStatus"])();
            setErrorInfo(null);
            // Gateway itself is reachable if we got a response
            const gatewayUp = data.status === 'healthy' || data.status === 'degraded';
            const next = {
                api_gateway: gatewayUp ? 'connected' : 'failed',
                data_collection: data.services?.data_collection === 'healthy' ? 'connected' : 'failed',
                ml_training: data.services?.ml_training === 'healthy' ? 'connected' : 'failed',
                prediction: data.services?.prediction === 'healthy' ? 'connected' : 'failed'
            };
            setServices(next);
            if (gatewayUp) {
                // Short delay so the user can see the green checks before transitioning
                setTimeout(()=>setReady(true), 600);
            }
        } catch (err) {
            const msg = err?.message || 'Network error';
            setErrorInfo(msg);
            setServices({
                api_gateway: 'failed',
                data_collection: 'failed',
                ml_training: 'failed',
                prediction: 'failed'
            });
        } finally{
            setChecking(false);
        }
    }, []);
    // Initial check
    (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__["useEffect"])(()=>{
        checkServices();
    }, [
        checkServices
    ]);
    // Auto-retry every 6s while not ready, up to 10 attempts
    (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react__$5b$external$5d$__$28$react$2c$__cjs$29$__["useEffect"])(()=>{
        if (ready) return;
        if (retryCount >= 10) return;
        const t = setTimeout(()=>{
            setRetryCount((c)=>c + 1);
            checkServices();
        }, 6000);
        return ()=>clearTimeout(t);
    }, [
        ready,
        retryCount,
        checkServices
    ]);
    const handleRetry = ()=>{
        setRetryCount(0);
        checkServices();
    };
    if (ready) {
        return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["Fragment"], {
            children: [
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$head$2e$js__$5b$ssr$5d$__$28$ecmascript$29$__["default"], {
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("title", {
                            children: "OTC Predictor - Live Trading Dashboard"
                        }, void 0, false, {
                            fileName: "[project]/frontend/pages/index.jsx",
                            lineNumber: 98,
                            columnNumber: 11
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("meta", {
                            name: "description",
                            content: "Real-time OTC trading dashboard with ML predictions"
                        }, void 0, false, {
                            fileName: "[project]/frontend/pages/index.jsx",
                            lineNumber: 99,
                            columnNumber: 11
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("meta", {
                            name: "viewport",
                            content: "width=device-width, initial-scale=1"
                        }, void 0, false, {
                            fileName: "[project]/frontend/pages/index.jsx",
                            lineNumber: 100,
                            columnNumber: 11
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("link", {
                            rel: "icon",
                            href: "/favicon.ico"
                        }, void 0, false, {
                            fileName: "[project]/frontend/pages/index.jsx",
                            lineNumber: 101,
                            columnNumber: 11
                        }, this)
                    ]
                }, void 0, true, {
                    fileName: "[project]/frontend/pages/index.jsx",
                    lineNumber: 97,
                    columnNumber: 9
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$frontend$2f$components$2f$PredictionDashboard$2e$jsx__$5b$ssr$5d$__$28$ecmascript$29$__["default"], {}, void 0, false, {
                    fileName: "[project]/frontend/pages/index.jsx",
                    lineNumber: 103,
                    columnNumber: 9
                }, this)
            ]
        }, void 0, true);
    }
    // Loading / connection screen
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["Fragment"], {
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$head$2e$js__$5b$ssr$5d$__$28$ecmascript$29$__["default"], {
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("title", {
                        children: "OTC Predictor - Connecting"
                    }, void 0, false, {
                        fileName: "[project]/frontend/pages/index.jsx",
                        lineNumber: 112,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("meta", {
                        name: "description",
                        content: "Real-time OTC trading dashboard"
                    }, void 0, false, {
                        fileName: "[project]/frontend/pages/index.jsx",
                        lineNumber: 113,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("meta", {
                        name: "viewport",
                        content: "width=device-width, initial-scale=1"
                    }, void 0, false, {
                        fileName: "[project]/frontend/pages/index.jsx",
                        lineNumber: 114,
                        columnNumber: 9
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/frontend/pages/index.jsx",
                lineNumber: 111,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                className: "startup-page",
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                    className: "startup-card",
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                            className: "startup-brand",
                            children: "OTC Predictor"
                        }, void 0, false, {
                            fileName: "[project]/frontend/pages/index.jsx",
                            lineNumber: 118,
                            columnNumber: 11
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("p", {
                            className: "startup-subtitle",
                            children: "Connecting to services..."
                        }, void 0, false, {
                            fileName: "[project]/frontend/pages/index.jsx",
                            lineNumber: 119,
                            columnNumber: 11
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                            className: "startup-services",
                            children: Object.entries(SERVICE_NAMES).map(([key, label])=>{
                                const status = services[key];
                                return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                                    className: "startup-service-row",
                                    children: [
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("span", {
                                            className: "startup-service-name",
                                            children: label
                                        }, void 0, false, {
                                            fileName: "[project]/frontend/pages/index.jsx",
                                            lineNumber: 126,
                                            columnNumber: 19
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("span", {
                                            className: `startup-service-badge ${status}`,
                                            children: [
                                                status === 'checking' && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("span", {
                                                    className: "startup-spinner"
                                                }, void 0, false, {
                                                    fileName: "[project]/frontend/pages/index.jsx",
                                                    lineNumber: 128,
                                                    columnNumber: 47
                                                }, this),
                                                status === 'connected' && 'Connected',
                                                status === 'failed' && (key === REQUIRED_SERVICE ? 'Unreachable' : 'Offline')
                                            ]
                                        }, void 0, true, {
                                            fileName: "[project]/frontend/pages/index.jsx",
                                            lineNumber: 127,
                                            columnNumber: 19
                                        }, this)
                                    ]
                                }, key, true, {
                                    fileName: "[project]/frontend/pages/index.jsx",
                                    lineNumber: 125,
                                    columnNumber: 17
                                }, this);
                            })
                        }, void 0, false, {
                            fileName: "[project]/frontend/pages/index.jsx",
                            lineNumber: 121,
                            columnNumber: 11
                        }, this),
                        errorInfo && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                            className: "startup-error-detail",
                            children: errorInfo
                        }, void 0, false, {
                            fileName: "[project]/frontend/pages/index.jsx",
                            lineNumber: 138,
                            columnNumber: 13
                        }, this),
                        services.api_gateway === 'failed' && !checking && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                            className: "startup-footer",
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("button", {
                                    className: "btn btn-primary",
                                    onClick: handleRetry,
                                    children: "Retry Connection"
                                }, void 0, false, {
                                    fileName: "[project]/frontend/pages/index.jsx",
                                    lineNumber: 146,
                                    columnNumber: 15
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                                    className: "startup-retry-info",
                                    children: retryCount < 10 ? `Auto-retrying... (${retryCount}/10)` : 'Auto-retry exhausted'
                                }, void 0, false, {
                                    fileName: "[project]/frontend/pages/index.jsx",
                                    lineNumber: 149,
                                    columnNumber: 15
                                }, this)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/frontend/pages/index.jsx",
                            lineNumber: 145,
                            columnNumber: 13
                        }, this),
                        services.api_gateway !== 'failed' && checking && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                            className: "startup-footer",
                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$externals$5d2f$react$2f$jsx$2d$dev$2d$runtime__$5b$external$5d$__$28$react$2f$jsx$2d$dev$2d$runtime$2c$__cjs$29$__["jsxDEV"])("div", {
                                className: "startup-retry-info",
                                children: "Checking services..."
                            }, void 0, false, {
                                fileName: "[project]/frontend/pages/index.jsx",
                                lineNumber: 160,
                                columnNumber: 15
                            }, this)
                        }, void 0, false, {
                            fileName: "[project]/frontend/pages/index.jsx",
                            lineNumber: 159,
                            columnNumber: 13
                        }, this)
                    ]
                }, void 0, true, {
                    fileName: "[project]/frontend/pages/index.jsx",
                    lineNumber: 117,
                    columnNumber: 9
                }, this)
            }, void 0, false, {
                fileName: "[project]/frontend/pages/index.jsx",
                lineNumber: 116,
                columnNumber: 7
            }, this)
        ]
    }, void 0, true);
}
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[externals]/next/dist/shared/lib/no-fallback-error.external.js [external] (next/dist/shared/lib/no-fallback-error.external.js, cjs)", ((__turbopack_context__, module, exports) => {

const mod = __turbopack_context__.x("next/dist/shared/lib/no-fallback-error.external.js", () => require("next/dist/shared/lib/no-fallback-error.external.js"));

module.exports = mod;
}),
];

//# sourceMappingURL=%5Broot-of-the-server%5D__bbd0f8cc._.js.map