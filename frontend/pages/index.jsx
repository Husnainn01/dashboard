import React from 'react';
import Head from 'next/head';
import Dashboard from '../components/Dashboard';

/**
 * Home page - Main entry point for the application
 */
export default function Home() {
  return (
    <div>
      <Head>
        <title>OTC Binary Trading Predictor</title>
        <meta name="description" content="Personal OTC binary trading prediction tool" />
        <link rel="icon" href="/favicon.ico" />
        <meta name="viewport" content="minimum-scale=1, initial-scale=1, width=device-width" />
      </Head>

      <main>
        <Dashboard />
      </main>
    </div>
  );
} 