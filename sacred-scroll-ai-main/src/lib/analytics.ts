import ReactGA from "react-ga4";

// Initialize Google Analytics
export const initGA = () => {
    // Replace with your actual Measurement ID or use an env var
    const MEASUREMENT_ID = import.meta.env.VITE_GA_MEASUREMENT_ID || "G-XXXXXXXXXX";
    if (MEASUREMENT_ID && MEASUREMENT_ID !== "G-XXXXXXXXXX") {
        ReactGA.initialize(MEASUREMENT_ID);
        console.log("GA Initialized with ID:", MEASUREMENT_ID);
    } else {
        console.warn("GA Measurement ID not found or is placeholder.");
    }
};

// Track Page View
export const trackPageView = (path: string) => {
    ReactGA.send({ hitType: "pageview", page: path });
};

// Track Custom Event
export const trackEvent = (category: string, action: string, label?: string) => {
    ReactGA.event({
        category,
        action,
        label,
    });
};
