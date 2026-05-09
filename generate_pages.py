import os

template_dir = r"c:\Users\Lenovo\OneDrive\Desktop\Logistic Tracker\templates"
with open(os.path.join(template_dir, 'home.html'), 'r', encoding='utf-8') as f:
    content = f.read()

header = content[:content.find('  <!-- HERO -->')]
footer = content[content.find('  <!-- FOOTER -->'):]

footer = footer.replace('© 2024 LogiControl India Private Limited.', '@2026 LogiControl Technologies Pvt Ltd.')

pages = {
    'help_center.html': ('Help Center', 'Find answers to your questions and learn how to use LogiControl.', '<i class="bi bi-question-circle"></i>'),
    'privacy_policy.html': ('Privacy Policy', 'Learn how we collect, use, and protect your data.', '<i class="bi bi-shield-lock"></i>'),
    'terms_of_service.html': ('Terms of Service', 'Read the terms and conditions for using LogiControl.', '<i class="bi bi-file-earmark-text"></i>'),
    'contact_support.html': ('Contact Support', 'Get in touch with our support team for any assistance.', '<i class="bi bi-envelope"></i>'),
}

for filename, (title, desc, icon) in pages.items():
    html = f"""{header}
  <section class="portal-section" style="min-height: 60vh;">
    <h2 class="section-title">{title}</h2>
    <p class="section-sub">{desc}</p>
    <div class="portal-card" style="max-width: 800px; text-align: left;">
      <div class="portal-icon">{icon}</div>
      <h3>{title}</h3>
      <p style="margin-top: 1.5rem; color: #334155; line-height: 1.8;">
        This page is under construction. Please check back later for full details regarding our {title.lower()}.
      </p>
    </div>
  </section>
{footer}"""
    with open(os.path.join(template_dir, filename), 'w', encoding='utf-8') as f:
        f.write(html)
print('Done!')
