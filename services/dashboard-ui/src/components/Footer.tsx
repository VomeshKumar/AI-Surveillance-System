import React from 'react';
import { Github, Linkedin, Twitter, Mail } from 'lucide-react';
import aiflowLogo from '../assets/aiflow-logo.png';

interface FooterLink {
  label: string;
  href: string;
}

interface FooterSection {
  title: string;
  links: FooterLink[];
}

interface SocialLink {
  icon: React.ReactNode;
  href: string;
  label: string;
}

interface FooterProps {
  sections?: FooterSection[];
  socialLinks?: SocialLink[];
  copyrightText?: string;
  companyName?: string;
  theme?: 'light' | 'dark';
}

export const Footer: React.FC<FooterProps> = ({
  sections = [
    {
      title: "Product",
      links: [
        { label: "Features", href: "#features" },
        { label: "Pricing", href: "#pricing" },
        { label: "Security", href: "#security" },
        { label: "API", href: "#api" },
      ],
    },
    {
      title: "Company",
      links: [
        { label: "About", href: "#about" },
        { label: "Blog", href: "#blog" },
        { label: "Careers", href: "#careers" },
        { label: "Contact", href: "#contact" },
      ],
    },
    {
      title: "Resources",
      links: [
        { label: "Documentation", href: "#docs" },
        { label: "Support", href: "#support" },
        { label: "Community", href: "#community" },
        { label: "Status", href: "#status" },
      ],
    },
  ],
  socialLinks = [
    { icon: <Github className="h-5 w-5" />, href: "#github", label: "GitHub" },
    { icon: <Twitter className="h-5 w-5" />, href: "#twitter", label: "Twitter" },
    { icon: <Linkedin className="h-5 w-5" />, href: "#linkedin", label: "LinkedIn" },
    { icon: <Mail className="h-5 w-5" />, href: "#email", label: "Email" },
  ],
  copyrightText = "All rights reserved.",
  companyName = "AIFLOW",
  theme = 'light',
}) => {
  const isDark = theme === 'dark';

  return (
    <footer className={`shrink-0 transition-colors ${isDark ? 'bg-slate-900 text-slate-100' : 'bg-black text-white'}`}>
      <div className="mx-auto max-w-7xl px-8 py-8">
        <div className="mb-6 grid grid-cols-1 gap-6 md:grid-cols-4">
          <div className="space-y-3">
            <div className="flex items-center">
              <img
                src={aiflowLogo}
                alt={companyName}
                className="h-10 w-auto rounded-lg object-contain"
              />
            </div>
            <p className={`text-xs leading-relaxed ${isDark ? 'text-slate-400' : 'text-gray-400'}`}>
              Secure transit networks with precision. Real-time facial recognition and threat orchestration.
            </p>
            <div className="flex gap-3 pt-1">
              {socialLinks.map((link) => (
                <a
                  key={link.label}
                  href={link.href}
                  aria-label={link.label}
                  className={`transition-colors duration-200 ${isDark ? 'text-slate-400 hover:text-slate-100' : 'text-gray-400 hover:text-white'}`}
                >
                  {link.icon}
                </a>
              ))}
            </div>
          </div>

          {sections.map((section) => (
            <div key={section.title} className="space-y-2">
              <h3 className={`text-xs font-semibold uppercase tracking-wide ${isDark ? 'text-slate-100' : 'text-white'}`}>
                {section.title}
              </h3>
              <ul className="space-y-1">
                {section.links.map((link) => (
                  <li key={link.label}>
                    <a
                      href={link.href}
                      className={`text-xs transition-colors duration-200 ${isDark ? 'text-slate-400 hover:text-slate-100' : 'text-gray-400 hover:text-white'}`}
                    >
                      {link.label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className={`border-t ${isDark ? 'border-slate-800' : 'border-gray-800'}`}></div>

        <div className="flex flex-col items-center justify-between gap-3 pt-4 md:flex-row">
          <p className={`text-xs ${isDark ? 'text-slate-400' : 'text-gray-400'}`}>
            © {new Date().getFullYear()} {companyName}. {copyrightText}
          </p>
          <div className="flex gap-4 text-xs">
            <a href="#privacy" className={isDark ? 'text-slate-400 transition-colors hover:text-slate-100' : 'text-gray-400 transition-colors hover:text-white'}>
              Privacy Policy
            </a>
            <a href="#terms" className={isDark ? 'text-slate-400 transition-colors hover:text-slate-100' : 'text-gray-400 transition-colors hover:text-white'}>
              Terms of Service
            </a>
            <a href="#cookies" className={isDark ? 'text-slate-400 transition-colors hover:text-slate-100' : 'text-gray-400 transition-colors hover:text-white'}>
              Cookie Settings
            </a>
          </div>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
