
import React from 'react';
import { useNavigate } from 'react-router-dom';

const PrivacyPolicy = () => {
    const navigate = useNavigate();

    return (
        <div className="flex flex-col h-full bg-background-light dark:bg-background-dark text-slate-900 dark:text-white overflow-y-auto">
            {/* Header */}
            <div className="p-6 flex items-center gap-4 border-b border-primary/10">
                <button
                    onClick={() => navigate(-1)}
                    className="p-2 rounded-full hover:bg-primary/10 transition-colors text-primary"
                >
                    <span className="material-symbols-outlined">arrow_back</span>
                </button>
                <h1 className="text-xl font-bold text-primary">Privacy Policy</h1>
            </div>

            {/* Content */}
            <div className="flex-1 p-6 max-w-3xl mx-auto space-y-8 pb-20">
                <section>
                    <h2 className="text-lg font-bold text-primary mb-3">1. Introduction</h2>
                    <p className="text-slate-600 dark:text-slate-300 leading-relaxed">
                        Welcome to AlQuran AI ("we," "our," or "us"). We are committed to protecting your privacy and ensuring your personal information is handled in a safe and responsible manner. This Privacy Policy explains how we collect, use, and protect your data.
                    </p>
                </section>

                <section>
                    <h2 className="text-lg font-bold text-primary mb-3">2. Information We Collect</h2>
                    <ul className="list-disc list-inside text-slate-600 dark:text-slate-300 space-y-2 leading-relaxed">
                        <li><strong>Account Information:</strong> When you sign in with Google, we collect your name, email address, and profile picture to create your account.</li>
                        <li><strong>Chat History:</strong> We store the conversations you have with our AI to provide you with access to your history and improve the service.</li>
                        <li><strong>Usage Data:</strong> We may collect anonymous data about how you use the app to improve performance and user experience.</li>
                    </ul>
                </section>

                <section>
                    <h2 className="text-lg font-bold text-primary mb-3">3. How We Use Your Information</h2>
                    <p className="text-slate-600 dark:text-slate-300 leading-relaxed">
                        We use your information to:
                    </p>
                    <ul className="list-disc list-inside text-slate-600 dark:text-slate-300 space-y-2 mt-2 leading-relaxed">
                        <li>Provide, maintain, and improve our services.</li>
                        <li>Personalize your experience (e.g., displaying your name).</li>
                        <li>Respond to your comments and questions.</li>
                    </ul>
                </section>

                <section>
                    <h2 className="text-lg font-bold text-primary mb-3">4. Data Security</h2>
                    <p className="text-slate-600 dark:text-slate-300 leading-relaxed">
                        We implement appropriate technical and organizational measures to protect your personal data against unauthorized access, alteration, disclosure, or destruction. However, no method of transmission over the Internet is 100% secure.
                    </p>
                </section>

                <section>
                    <h2 className="text-lg font-bold text-primary mb-3">5. Contact Us</h2>
                    <p className="text-slate-600 dark:text-slate-300 leading-relaxed">
                        If you have any questions about this Privacy Policy, please contact us at <a href="mailto:support@quranai.com" className="text-primary hover:underline">support@quranai.com</a>.
                    </p>
                </section>

                <div className="text-center pt-8 text-xs text-slate-400">
                    Last Updated: October 2024
                </div>
            </div>
        </div>
    );
};

export default PrivacyPolicy;
