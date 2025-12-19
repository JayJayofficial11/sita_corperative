// COMPLETELY DISABLE ALL SPINNER OVERLAYS
// This script aggressively removes all spinner functionality

(function() {
    'use strict';
    
    // Remove all existing spinner overlays
    function removeAllSpinners() {
        const spinners = document.querySelectorAll('.spinner-overlay, [class*="spinner-overlay"], [class*="spinner-border"]');
        spinners.forEach(spinner => {
            spinner.remove();
        });
    }
    
    // Override any spinner functions globally
    window.showLoadingSpinner = function() {
        // Do nothing - completely disabled
        return;
    };
    
    window.hideLoadingSpinner = function() {
        // Do nothing - completely disabled
        return;
    };
    
    // Remove spinners on page load
    document.addEventListener('DOMContentLoaded', function() {
        removeAllSpinners();
        
        // Remove spinners every 100ms to catch any that appear
        setInterval(removeAllSpinners, 100);
    });
    
    // Remove spinners immediately
    removeAllSpinners();
    
    // Override any form submission handlers that might add spinners
    document.addEventListener('submit', function(e) {
        // Remove any spinners that might have been added
        setTimeout(removeAllSpinners, 10);
    });
    
    console.log('🚫 All spinner overlays have been completely disabled');
})();
