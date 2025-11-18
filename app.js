// Initialize Socket.IO
const socket = io();

// Application State (using in-memory JavaScript variables instead of localStorage)
window.appState = {
  products: [],
  sites: [
    {
      name: 'Wildberries',
      url: 'https://www.wildberries.ru/catalog/0/search.aspx?search=',
      selectors: {
        title: 'article[id^="c"] heading generic::text',
        price: 'article[id^="c"] generic::text',
        link: 'article[id^="c"] a::attr(href)'
      },
      active: true
    },
    {
      name: 'Ozon',
      url: 'https://www.ozon.ru/search/?text=',
      selectors: {
        title: 'span[class*="tsBody"]::text',
        price: '[data-widget="webPrice"] span::text',
        link: 'a[href*="/product/"]::attr(href)'
      },
      active: true
    },
    {
      name: 'Avito',
      url: 'https://www.avito.ru/all?q=',
      selectors: {
        title: '[itemprop="name"]::text',
        price: '[class*="iva-item-price"] span::text',
        link: 'a[itemprop="url"]::attr(href)'
      },
      active: true
    },
    {
      name: 'Yandex.Market',
      url: 'https://market.yandex.ru/search?text=',
      selectors: {
        title: '.product-title::text',
        price: '.price::text',
        link: 'a.product-link::attr(href)'
      },
      active: true
    },
    {
      name: 'Mr-moto.ru',
      url: 'https://mr-moto.ru/search/?q=',
      selectors: {
        title: '.product-name::text',
        price: '.price::text',
        link: 'a.product-link::attr(href)'
      },
      active: true
    },
    {
      name: 'Flipup.ru',
      url: 'http://flipup.ru/search?q=',
      selectors: {
        title: '.product-title::text',
        price: '.product-price::text',
        link: 'a.product-url::attr(href)'
      },
      active: false
    },
    {
      name: 'Pro-ekip.ru',
      url: 'http://pro-ekip.ru/search?q=',
      selectors: {
        title: '.item-title::text',
        price: '.item-price::text',
        link: 'a.item-link::attr(href)'
      },
      active: false
    },
    {
      name: 'Motoekip.su',
      url: 'http://motoekip.su/search?q=',
      selectors: {
        title: '.goods-name::text',
        price: '.goods-price::text',
        link: 'a.goods-link::attr(href)'
      },
      active: false
    },
    {
      name: 'Motocomfort.ru',
      url: 'http://motocomfort.ru/search?q=',
      selectors: {
        title: '.product-name::text',
        price: '.product-price::text',
        link: 'a.product-url::attr(href)'
      },
      active: false
    }
  ],
  matchingConfig: {
    threshold: 85,
    weights: {
      name: 0.6,
      brand: 0.2,
      size: 0.2
    }
  },
  results: [],
  currentSiteConfig: null
};

// DOM Elements
const uploadZone = document.getElementById('uploadZone');
const fileInput = document.getElementById('fileInput');
const selectFileBtn = document.getElementById('selectFileBtn');
const startAnalysisBtn = document.getElementById('startAnalysisBtn');
const fileInfo = document.getElementById('fileInfo');
const fileName = document.getElementById('fileName');
const productCount = document.getElementById('productCount');
const sitesGrid = document.getElementById('sitesGrid');
const thresholdSlider = document.getElementById('thresholdSlider');
const thresholdValue = document.getElementById('thresholdValue');
// This line was removed as we're using startAnalysisBtn instead
const progressContainer = document.getElementById('progressContainer');
const progressFill = document.getElementById('progressFill');
const progressText = document.getElementById('progressText');
const stepResults = document.getElementById('step-results');
const resultsTableBody = document.getElementById('resultsTableBody');
const searchInput = document.getElementById('searchInput');
const siteFilter = document.getElementById('siteFilter');
const exportBtn = document.getElementById('exportBtn');
const exportGoogleBtn = document.getElementById('exportGoogleBtn');
const matchModal = document.getElementById('matchModal');
const closeModal = document.getElementById('closeModal');
const modalBody = document.getElementById('modalBody');
const siteConfigModal = document.getElementById('siteConfigModal');
const closeSiteConfigModal = document.getElementById('closeSiteConfigModal');

// Initialize button references if they don't exist
if (!startAnalysisBtn) {
  console.error('Start Analysis button not found in the DOM');
  // Try to find it again later when the DOM is fully loaded
  document.addEventListener('DOMContentLoaded', () => {
    window.startAnalysisBtn = document.getElementById('startAnalysisBtn');
    if (!window.startAnalysisBtn) {
      console.error('Start Analysis button still not found after DOM loaded');
    } else {
      console.log('Start Analysis button found after DOM loaded');
    }
  });
}

// Initialize App
function init() {
  // Wait for DOM to be fully loaded
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      initializeApp();
    });
  } else {
    initializeApp();
  }
}

function initializeApp() {
  renderSites();
  setupEventListeners();
  updateSiteFilter();
  
  // Check if we already have products in the state
  checkAnalysisReady();
  
  // Log initial state
  console.log('Initial app state:', {
    products: appState.products,
    sites: appState.sites,
    hasActiveSites: appState.sites.some(s => s.active)
  });
}

// Event Listeners
function setupEventListeners() {
  // File upload
  if (uploadZone && fileInput) {
    uploadZone.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', handleFileUpload);
  }
  
  if (selectFileBtn && fileInput) {
    selectFileBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      fileInput.click();
    });
  }

  // Drag and drop
  uploadZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadZone.style.borderColor = 'var(--color-primary)';
  });
  uploadZone.addEventListener('dragleave', () => {
    uploadZone.style.borderColor = '';
  });
  uploadZone.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadZone.style.borderColor = '';
    if (e.dataTransfer.files.length) {
      fileInput.files = e.dataTransfer.files;
      handleFileUpload();
    }
  });

  // Max products slider
  const maxProductsSlider = document.getElementById('maxProductsSlider');
  const maxProductsValue = document.getElementById('maxProductsValue');
  if (maxProductsSlider && maxProductsValue) {
    maxProductsSlider.addEventListener('input', (e) => {
      maxProductsValue.textContent = e.target.value;
    });
  }

  // Threshold slider
  thresholdSlider.addEventListener('input', (e) => {
    appState.matchingConfig.threshold = parseInt(e.target.value);
    thresholdValue.textContent = e.target.value;
  });

  // Run analysis
  if (startAnalysisBtn) {
    startAnalysisBtn.addEventListener('click', runAnalysis);
  }

  // Search and filter
  searchInput.addEventListener('input', debounce(filterResults, 300));
  siteFilter.addEventListener('change', filterResults);

  // Export
  exportBtn.addEventListener('click', exportResults);
  if (exportGoogleBtn) {
    exportGoogleBtn.addEventListener('click', exportToGoogleSheets);
  }

  // Modals
  closeModal.addEventListener('click', () => matchModal.classList.remove('active'));
  closeSiteConfigModal.addEventListener('click', () => siteConfigModal.classList.remove('active'));
  matchModal.addEventListener('click', (e) => {
    if (e.target === matchModal) matchModal.classList.remove('active');
  });
  siteConfigModal.addEventListener('click', (e) => {
    if (e.target === siteConfigModal) siteConfigModal.classList.remove('active');
  });

  // Save site config
  document.getElementById('saveSiteConfig').addEventListener('click', saveSiteConfig);
}

// File Upload Handler
function handleFileUpload() {
  const file = fileInput.files[0];
  if (!file) return;

  const fileExt = file.name.split('.').pop().toLowerCase();
  if (!['xlsx', 'xls', 'xml'].includes(fileExt)) {
    alert('Пожалуйста, выберите файл Excel (.xlsx, .xls) или XML');
    return;
  }

  // Show file info and progress
  const fileName = document.getElementById('fileName');
  const fileInfo = document.getElementById('fileInfo');
  const progressContainer = document.getElementById('progressContainer');
  const progressFill = document.getElementById('progressFill');
  const progressText = document.getElementById('progressText');
  
  fileName.textContent = file.name;
  fileInfo.style.display = 'block';
  progressContainer.style.display = 'block';
  progressFill.style.width = '0%';
  progressText.textContent = 'Начало загрузки...';
  
  processFile(file);
}

function processFile(file) {
  const formData = new FormData();
  formData.append('file', file);
  
  // Show loading state
  const fileInfo = document.getElementById('fileInfo');
  const productCount = document.getElementById('productCount');
  const progressContainer = document.getElementById('progressContainer');
  const progressFill = document.getElementById('progressFill');
  const progressText = document.getElementById('progressText');
  
  fileInfo.style.display = 'block';
  productCount.textContent = 'загрузка...';
  progressContainer.style.display = 'block';
  progressFill.style.width = '0%';
  progressText.textContent = 'Начало загрузки...';
  
  // Send file to server for processing
  fetch('/api/upload-xml', {
    method: 'POST',
    body: formData
  })
  .then(response => response.json())
  .then(data => {
    console.log('File upload response:', data);
    if (data.success) {
      // Ensure window.appState exists
      window.appState = window.appState || { products: [], sites: [] };
      
      // Update products in appState
      window.appState.products = data.products || [];
      
      // Update UI
      if (productCount) {
        productCount.textContent = window.appState.products.length;
      }
      
      console.log('Products after upload:', window.appState.products);
      
      // Show success message
      showNotification(`Успешно загружено ${window.appState.products.length} товаров`, 'success');
      
      // Update progress to complete
      if (progressFill) progressFill.style.width = '100%';
      if (progressFill) progressFill.style.backgroundColor = '#28a745';
      if (progressText) progressText.textContent = 'Завершено';
      
      // Initialize sites if not exists
      if (!window.appState.sites || !Array.isArray(window.appState.sites)) {
        window.appState.sites = [
          { name: 'Wildberries', url: 'https://www.wildberries.ru/catalog/0/search.aspx?search=', active: true },
          { name: 'Ozon', url: 'https://www.ozon.ru/search/?text=', active: true },
          { name: 'Avito', url: 'https://www.avito.ru/all?q=', active: true }
        ];
      }
      
      // Make sure we have active sites
      if (window.appState.sites.every(s => !s.active)) {
        // If no active sites, activate the first one by default
        window.appState.sites[0].active = true;
        if (typeof renderSites === 'function') {
          renderSites();
        }
      }
      
      console.log('Updated appState:', JSON.parse(JSON.stringify(window.appState)));
      
      // Update the button state
      setTimeout(checkAnalysisReady, 100); // Small delay to ensure DOM is updated
    } else {
      // Show error message
      showNotification(data.error || 'Ошибка при загрузке файла', 'error');
      progressFill.style.backgroundColor = '#dc3545';
      progressText.textContent = `Ошибка: ${data.error || 'Неизвестная ошибка'}`;
    }
    
    // Enable analysis if we have products and at least one site is active
    checkAnalysisReady();
  })
  .catch(error => {
    console.error('Error uploading file:', error);
    showNotification('Ошибка при загрузке файла', 'error');
    progressFill.style.backgroundColor = '#dc3545';
    progressText.textContent = `Ошибка: ${error.message || 'Неизвестная ошибка'}`;
  });
}

// Handle progress updates from server
socket.on('progress_update', (data) => {
  const progressContainer = document.getElementById('progressContainer');
  const progressFill = document.getElementById('progressFill');
  const progressText = document.getElementById('progressText');
  
  progressContainer.style.display = 'block';
  
  if (data.stage === 'error') {
    progressFill.style.width = '100%';
    progressFill.style.backgroundColor = '#dc3545';
    progressText.textContent = `Ошибка: ${data.message}`;
    return;
  }
  
  if (data.stage === 'complete') {
    progressFill.style.width = '100%';
    progressFill.style.backgroundColor = '#28a745';
    progressText.textContent = 'Завершено';
    return;
  }
  
  const progress = data.progress || 0;
  progressFill.style.width = `${progress}%`;
  progressText.textContent = `${data.message} (${Math.round(progress)}%)`;
  
  // Update progress bar color based on progress
  if (progress < 30) {
    progressFill.style.backgroundColor = '#dc3545';
  } else if (progress < 70) {
    progressFill.style.backgroundColor = '#ffc107';
  } else {
    progressFill.style.backgroundColor = '#28a745';
  }
});

// Parse XML (simplified - in real app would parse actual CommerceML)
function parseXML(xmlString) {
  // This function is not used in the current implementation
  // XML parsing is handled by the server
  console.log('XML parsing is handled by the server');
}

// Render Sites
function renderSites() {
  sitesGrid.innerHTML = appState.sites.map((site, index) => `
    <div class="site-card ${site.active ? 'active' : ''}" data-index="${index}">
      <div class="site-card-header">
        <div class="site-name">${site.name}</div>
        <div class="checkbox-wrapper">
          <input type="checkbox" ${site.active ? 'checked' : ''} 
                 onchange="toggleSite(${index})" 
                 id="site-${index}">
        </div>
      </div>
      <div class="site-url">${site.url}</div>
      <button class="btn btn--secondary site-config-btn" onclick="openSiteConfig(${index})">
        Настроить селекторы
      </button>
    </div>
  `).join('');
}

// Toggle Site
window.toggleSite = function(index) {
  appState.sites[index].active = !appState.sites[index].active;
  renderSites();
  checkAnalysisReady();
};

// Open Site Config
window.openSiteConfig = function(index) {
  appState.currentSiteConfig = index;
  const site = appState.sites[index];
  
  document.getElementById('titleSelector').value = site.selectors.title;
  document.getElementById('priceSelector').value = site.selectors.price;
  document.getElementById('linkSelector').value = site.selectors.link;
  
  siteConfigModal.classList.add('active');
};

// Save Site Config
function saveSiteConfig() {
  const index = appState.currentSiteConfig;
  if (index === null) return;

  appState.sites[index].selectors = {
    title: document.getElementById('titleSelector').value,
    price: document.getElementById('priceSelector').value,
    link: document.getElementById('linkSelector').value
  };

  siteConfigModal.classList.remove('active');
  alert('Настройки сохранены');
}

// Check if analysis is ready
function checkAnalysisReady() {
  try {
    // Ensure appState is properly initialized
    window.appState = window.appState || {};
    window.appState.products = window.appState.products || [];
    window.appState.sites = window.appState.sites || [
      { name: 'Wildberries', url: 'https://www.wildberries.ru/catalog/0/search.aspx?search=', active: true },
      { name: 'Ozon', url: 'https://www.ozon.ru/search/?text=', active: true },
      { name: 'Avito', url: 'https://www.avito.ru/all?q=', active: true }
    ];
    
    const state = window.appState;
    const hasProducts = state.products && state.products.length > 0;
    const hasActiveSites = state.sites && state.sites.some(s => s && s.active);
    const shouldEnable = hasProducts && hasActiveSites;
    
    // Try to find the button if it's not already available
    const startBtn = document.getElementById('startAnalysisBtn');
    
    console.log('checkAnalysisReady:', {
      hasProducts,
      hasActiveSites,
      shouldEnable,
      productsCount: state.products ? state.products.length : 0,
      activeSites: state.sites ? state.sites.filter(s => s && s.active).length : 0,
      startBtnFound: !!startBtn,
      state: JSON.parse(JSON.stringify(state)) // Simple clone for logging
    });
    
    if (startBtn) {
      startBtn.disabled = !shouldEnable;
      console.log(`Button state updated: disabled=${startBtn.disabled}`);
      
      // If we have the button but it's still disabled, check if we need to render sites
      if (startBtn.disabled && hasProducts && (!state.sites || state.sites.length === 0)) {
        console.log('Products exist but no sites found. Initializing default sites...');
        if (typeof renderSites === 'function') {
          renderSites();
          // Check again after rendering sites
          setTimeout(checkAnalysisReady, 100);
        }
      }
    } else {
      console.error('Start Analysis button not found in checkAnalysisReady');
      // Try to find it again in the next tick
      setTimeout(() => {
        const btn = document.getElementById('startAnalysisBtn');
        if (btn) {
          console.log('Found button in delayed check');
          btn.disabled = !shouldEnable;
        }
      }, 100);
    }
    
    return shouldEnable;
  } catch (error) {
    console.error('Error in checkAnalysisReady:', error);
    const startAnalysisBtn = document.getElementById('startAnalysisBtn');
    if (startAnalysisBtn) startAnalysisBtn.disabled = true;
    return false;
  }
}

// Run Analysis
async function runAnalysis() {
  const startAnalysisBtn = document.getElementById('startAnalysisBtn');
  const progressContainer = document.getElementById('progressContainer');
  const progressFill = document.getElementById('progressFill');
  const progressText = document.getElementById('progressText');
  
  if (!startAnalysisBtn) {
    console.error('Start Analysis button not found');
    return;
  }
  
  try {
    // Disable button and show loading state
    startAnalysisBtn.disabled = true;
    startAnalysisBtn.textContent = 'Выполняется...';
    
    if (progressContainer) progressContainer.style.display = 'block';
    if (progressFill) progressFill.style.width = '0%';
    if (progressText) progressText.textContent = 'Начало анализа...';
    
    const threshold = parseFloat(document.getElementById('thresholdSlider').value) / 100;
    const maxProducts = parseInt(document.getElementById('maxProductsSlider').value);
    
    // Собираем выбранные сайты
    const siteNameMap = {
      'Wildberries': 'wildberries',
      'Ozon': 'ozon',
      'Avito': 'avito',
      'Yandex.Market': 'yandex_market',
      'Mr-moto.ru': 'mr-moto'
    };
    
    const activeSites = appState.sites
      .filter(site => site.active)
      .map(site => siteNameMap[site.name] || site.name.toLowerCase().replace(/[.\s-]/g, ''));
    
    console.log('Параметры анализа:', {
      threshold,
      maxProducts,
      sites: activeSites
    });
    
    // Make API call to start analysis
    const response = await fetch('/api/run-analysis', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        threshold: threshold,
        max_products: maxProducts,
        sites: activeSites.length > 0 ? activeSites : null
      })
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Ошибка при запуске анализа');
    }
    
    const data = await response.json();
    
    // Update progress to 100%
    if (progressFill) progressFill.style.width = '100%';
    if (progressText) progressText.textContent = '100%';
    
    // Show success message
    showNotification('Анализ успешно завершен!', 'success');
    
    // Update results
    if (data.report && data.report.matches && Array.isArray(data.report.matches)) {
      // Group matches by product_1c_id
      const matchesByProduct = {};
      
      data.report.matches.forEach(match => {
        const productId = match.product_1c_id || match['product_1c_id'] || '';
        if (!matchesByProduct[productId]) {
          matchesByProduct[productId] = {
            product: {
              name: match.product_1c_name || match['product_1c_name'] || '',
              article: match.product_1c_id || match['product_1c_id'] || '',
              price: match.price_1c || match['price_1c'] || 0,
              stock: 0
            },
            matches: []
          };
        }
        
        matchesByProduct[productId].matches.push({
          site: match.marketplace || match['marketplace'] || '',
          title: match.scraped_product_title || match['scraped_product_title'] || '',
          price: match.price_scraped || match['price_scraped'] || 0,
          url: match.url || match['url'] || '',
          similarity: Math.round((match.similarity_score || match['similarity_score'] || 0) * 100)
        });
      });
      
      // Convert to array
      appState.results = Object.values(matchesByProduct);
      
      // Если нет совпадений, но есть товары из 1С - показываем их
      if (appState.results.length === 0 && data.report.products_1c && data.report.products_1c.length > 0) {
        console.log('Нет совпадений, показываем товары из 1С');
        appState.results = data.report.products_1c.slice(0, 10).map(product => ({
          product: {
            name: product.name || '',
            article: product.id || '',
            price: product.price || 0,
            stock: 0
          },
          matches: []
        }));
      }
    } else {
      appState.results = [];
      
      // Если совсем нет данных, но есть товары из 1С
      if (data.report && data.report.products_1c && data.report.products_1c.length > 0) {
        console.log('Нет matches, показываем товары из 1С');
        appState.results = data.report.products_1c.slice(0, 10).map(product => ({
          product: {
            name: product.name || '',
            article: product.id || '',
            price: product.price || 0,
            stock: 0
          },
          matches: []
        }));
      }
    }
    
    // Показываем статистику
    if (data.report && data.report.summary) {
      const summary = data.report.summary;
      console.log(`📊 Статистика: ${summary.total_products_1c} товаров из 1С, ${summary.total_scraped_products} найдено, ${summary.total_matches} совпадений`);
      
      if (summary.total_matches === 0) {
        showNotification(`⚠️ Совпадений не найдено. Попробуйте снизить порог совпадения до 60-70%`, 'warning');
      }
    }
    
    showResults();
    
  } catch (error) {
    console.error('Ошибка при выполнении анализа:', error);
    showNotification(`Ошибка: ${error.message}`, 'error');
    if (progressFill) progressFill.style.backgroundColor = '#dc3545';
    if (progressText) progressText.textContent = `Ошибка: ${error.message}`;
  } finally {
    // Reset button state
    if (startAnalysisBtn) {
      startAnalysisBtn.disabled = false;
      startAnalysisBtn.textContent = 'Запустить парсинг';
    }
  }
}

// Show Notification
function showNotification(message, type = 'info') {
  // Create notification element
  const notification = document.createElement('div');
  notification.className = `notification notification--${type}`;
  notification.textContent = message;
  const colors = {
    'success': '#28a745',
    'error': '#dc3545',
    'warning': '#ffc107',
    'info': '#17a2b8'
  };
  
  notification.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    padding: 12px 24px;
    background: ${colors[type] || colors.info};
    color: ${type === 'warning' ? '#000' : 'white'};
    border-radius: 4px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.2);
    z-index: 10000;
    animation: slideIn 0.3s ease-out;
    font-weight: 500;
  `;
  
  // Add animation
  const style = document.createElement('style');
  style.textContent = `
    @keyframes slideIn {
      from {
        transform: translateX(100%);
        opacity: 0;
      }
      to {
        transform: translateX(0);
        opacity: 1;
      }
    }
  `;
  if (!document.getElementById('notification-style')) {
    style.id = 'notification-style';
    document.head.appendChild(style);
  }
  
  document.body.appendChild(notification);
  
  // Remove after 3 seconds
  setTimeout(() => {
    notification.style.animation = 'slideIn 0.3s ease-out reverse';
    setTimeout(() => {
      if (notification.parentNode) {
        notification.parentNode.removeChild(notification);
      }
    }, 300);
  }, 3000);
}

// Simulate Scraping (in production, would make actual requests)
function simulateScraping(product, site) {
  const matches = [];
  const shouldFind = Math.random() > 0.3; // 70% chance of finding something

  if (shouldFind) {
    const numMatches = Math.floor(Math.random() * 3) + 1;
    for (let i = 0; i < numMatches; i++) {
      const priceVariation = (Math.random() - 0.5) * 0.3; // ±15%
      const similarityScore = Math.floor(Math.random() * 20) + 80; // 80-100%
      
      if (similarityScore >= appState.matchingConfig.threshold) {
        matches.push({
          site: site.name,
          title: product.name + (i > 0 ? ` (вариант ${i + 1})` : ''),
          price: Math.floor(product.price * (1 + priceVariation)),
          url: site.url + encodeURIComponent(product.name),
          similarity: similarityScore
        });
      }
    }
  }

  return matches;
}

// Update Progress
function updateProgress(percentage) {
  progressFill.style.width = percentage + '%';
  progressText.textContent = `Обработано: ${Math.floor(percentage)}%`;
}

// Show Results
function showResults() {
  stepResults.style.display = 'block';
  updateSiteFilter();
  renderResults();
  stepResults.scrollIntoView({ behavior: 'smooth' });
}

// Update Site Filter
function updateSiteFilter() {
  const activeSites = appState.sites.filter(s => s.active);
  siteFilter.innerHTML = `
    <option value="all">Все сайты</option>
    ${activeSites.map(site => `<option value="${site.name}">${site.name}</option>`).join('')}
  `;
}

// Render Results
function renderResults() {
  const searchTerm = searchInput.value.toLowerCase();
  const selectedSite = siteFilter.value;

  const filteredResults = appState.results.filter(result => {
    const matchesSearch = result.product.name.toLowerCase().includes(searchTerm) ||
                         result.product.article.toLowerCase().includes(searchTerm);
    return matchesSearch;
  });

  resultsTableBody.innerHTML = filteredResults.map((result, index) => {
    let matches = result.matches;
    if (selectedSite !== 'all') {
      matches = matches.filter(m => m.site === selectedSite);
    }

    const minPrice = matches.length > 0 ? Math.min(...matches.map(m => m.price)) : null;
    const priceDiff = minPrice ? result.product.price - minPrice : null;
    const diffClass = priceDiff > 0 ? 'positive' : priceDiff < 0 ? 'negative' : '';

    return `
      <tr>
        <td>${result.product.name}</td>
        <td>${result.product.article}</td>
        <td>${formatPrice(result.product.price)}</td>
        <td>${result.product.stock}</td>
        <td>
          ${matches.length > 0 ? 
            `<span class="status status--success">${matches.length} найдено</span>` :
            `<span class="status status--error">Не найдено</span>`
          }
        </td>
        <td>${minPrice ? formatPrice(minPrice) : '—'}</td>
        <td>
          ${priceDiff !== null ? 
            `<span class="price-difference ${diffClass}">${priceDiff > 0 ? '+' : ''}${formatPrice(priceDiff)}</span>` :
            '—'
          }
        </td>
        <td>
          ${matches.length > 0 ? 
            `<button class="btn btn--secondary btn--sm" onclick="showMatchDetails(${index})">Детали</button>` :
            '—'
          }
        </td>
      </tr>
    `;
  }).join('');
}

// Show Match Details
window.showMatchDetails = function(resultIndex) {
  const result = appState.results[resultIndex];
  const selectedSite = siteFilter.value;
  let matches = result.matches;
  
  if (selectedSite !== 'all') {
    matches = matches.filter(m => m.site === selectedSite);
  }

  modalBody.innerHTML = `
    <h4 style="margin-bottom: 16px;">${result.product.name}</h4>
    <p style="margin-bottom: 20px; color: var(--color-text-secondary);">
      Цена в 1С: <strong>${formatPrice(result.product.price)}</strong>
    </p>
    ${matches.map(match => `
      <div class="match-item">
        <div class="match-header">
          <span class="match-site">${match.site}</span>
          <span class="match-similarity">${match.similarity}% совпадение</span>
        </div>
        <div class="match-title">${match.title}</div>
        <div class="match-price">${formatPrice(match.price)}</div>
        <a href="${match.url}" target="_blank" class="match-link">Открыть на сайте →</a>
      </div>
    `).join('')}
  `;

  matchModal.classList.add('active');
};

// Filter Results
function filterResults() {
  renderResults();
}

// Export Results
async function exportResults() {
  try {
    showNotification('Экспорт отчета...', 'info');
    
    const response = await fetch('/api/export-report', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        format: 'csv'
      })
    });
    
    if (!response.ok) {
      throw new Error('Ошибка при экспорте отчета');
    }
    
    const data = await response.json();
    
    if (data.success) {
      showNotification(`Отчет сохранен: ${data.report_path}`, 'success');
      
      // Скачиваем файл
      const downloadLink = document.createElement('a');
      downloadLink.href = `/api/download-report?path=${encodeURIComponent(data.report_path)}`;
      downloadLink.download = data.report_path.split(/[/\\]/).pop();
      document.body.appendChild(downloadLink);
      downloadLink.click();
      document.body.removeChild(downloadLink);
    }
  } catch (error) {
    console.error('Ошибка экспорта:', error);
    showNotification(`Ошибка: ${error.message}`, 'error');
  }
}

// Export to Google Sheets
async function exportToGoogleSheets() {
  try {
    // Запрашиваем ID таблицы у пользователя
    const spreadsheetId = prompt(
      'Введите ID Google Таблицы:\n\n' +
      'ID можно найти в URL таблицы:\n' +
      'https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit\n\n' +
      'Пример: 1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms'
    );
    
    if (!spreadsheetId || spreadsheetId.trim() === '') {
      showNotification('ID таблицы не указан', 'warning');
      return;
    }
    
    // Убираем лишние пробелы и извлекаем ID из URL если пользователь ввел полный URL
    let cleanId = spreadsheetId.trim();
    const urlMatch = cleanId.match(/\/spreadsheets\/d\/([a-zA-Z0-9-_]+)/);
    if (urlMatch) {
      cleanId = urlMatch[1];
    }
    
    showNotification('Экспорт в Google Таблицу...', 'info');
    
    const response = await fetch('/api/export-google-sheets', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        spreadsheet_id: cleanId
      })
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ error: 'Неизвестная ошибка' }));
      
      // Специальная обработка ошибок подключения
      if (errorData.type === 'connection_error' || response.status === 503) {
        const errorMsg = errorData.error || 'Ошибка подключения к Google Sheets API';
        showNotification(
          'Ошибка подключения к интернету. Проверьте:\n' +
          '1. Подключение к интернету\n' +
          '2. Настройки DNS\n' +
          '3. Брандмауэр и антивирус',
          'error'
        );
        throw new Error(errorMsg);
      }
      
      throw new Error(errorData.error || 'Ошибка при экспорте в Google Таблицу');
    }
    
    const data = await response.json();
    
    if (data.success) {
      showNotification('Данные успешно экспортированы в Google Таблицу!', 'success');
      
      // Показываем ссылку на таблицу
      if (data.spreadsheet_url) {
        const openLink = confirm(
          'Экспорт завершен успешно!\n\n' +
          'Открыть таблицу в браузере?'
        );
        if (openLink) {
          window.open(data.spreadsheet_url, '_blank');
        }
      }
    } else {
      throw new Error(data.error || 'Неизвестная ошибка');
    }
  } catch (error) {
    console.error('Ошибка экспорта в Google Sheets:', error);
    showNotification(`Ошибка: ${error.message}`, 'error');
  }
}

// Generate CSV (legacy - для локального экспорта)
function generateCSV() {
  const headers = ['Товар 1С', 'Артикул', 'Цена 1С (руб)', 'Маркетплейс', 'Название на маркетплейсе', 'Цена конкурента (руб)', 'Разница (руб)', 'Разница (%)', 'Совпадение (%)', 'Ссылка'];
  const rows = [];
  
  appState.results.forEach(result => {
    if (result.matches.length > 0) {
      result.matches.forEach(match => {
        const priceDiff = match.price - result.product.price;
        const priceDiffPercent = ((priceDiff / result.product.price) * 100).toFixed(1);
        
        rows.push([
          result.product.name,
          result.product.article,
          result.product.price,
          match.site,
          match.title,
          match.price,
          priceDiff.toFixed(2),
          priceDiffPercent,
          match.similarity,
          match.url || ''
        ]);
      });
    } else {
      rows.push([
        result.product.name,
        result.product.article,
        result.product.price,
        'Не найдено',
        '',
        '',
        '',
        '',
        '',
        ''
      ]);
    }
  });

  return [headers, ...rows].map(row => row.join(',')).join('\n');
}

// Utility Functions
function formatPrice(price) {
  return new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'RUB',
    minimumFractionDigits: 0
  }).format(price);
}

function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

// Fuzzy Matching Algorithm (Levenshtein distance)
function levenshteinDistance(str1, str2) {
  const matrix = [];
  
  for (let i = 0; i <= str2.length; i++) {
    matrix[i] = [i];
  }
  
  for (let j = 0; j <= str1.length; j++) {
    matrix[0][j] = j;
  }
  
  for (let i = 1; i <= str2.length; i++) {
    for (let j = 1; j <= str1.length; j++) {
      if (str2.charAt(i - 1) === str1.charAt(j - 1)) {
        matrix[i][j] = matrix[i - 1][j - 1];
      } else {
        matrix[i][j] = Math.min(
          matrix[i - 1][j - 1] + 1,
          matrix[i][j - 1] + 1,
          matrix[i - 1][j] + 1
        );
      }
    }
  }
  
  return matrix[str2.length][str1.length];
}

function calculateSimilarity(str1, str2) {
  const distance = levenshteinDistance(str1.toLowerCase(), str2.toLowerCase());
  const maxLength = Math.max(str1.length, str2.length);
  return ((maxLength - distance) / maxLength) * 100;
}

// Initialize the application
init();