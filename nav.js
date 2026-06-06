// Shared navigation for londonschool.directory
// Place this file at the root of the repo and load it from any page
(function() {
  const currentPath = window.location.pathname;

  const navHTML = `
<header class="site" id="site-header">
  <div class="inner">
    <a class="brand" href="/">London School Directory</a>
    <nav>
      <a href="/" ${currentPath === '/' ? 'class="active"' : ''}>Search</a>
      <a href="/schools/" ${currentPath.startsWith('/schools/') ? 'class="active"' : ''}>Boroughs</a>
      <a href="/appeals.html" ${currentPath.includes('appeals') ? 'class="active"' : ''}>Appeals</a>
      <a href="/guides/" ${currentPath.startsWith('/guides/') ? 'class="active"' : ''}>Guides</a>
      <a href="/methodology.html" ${currentPath.includes('methodology') ? 'class="active"' : ''}>Methodology</a>
    </nav>
  </div>
</header>`;

  // Insert nav at top of body
  document.body.insertAdjacentHTML('afterbegin', navHTML);
