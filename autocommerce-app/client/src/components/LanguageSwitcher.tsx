import React, { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Globe } from 'lucide-react';

interface LanguageOption {
  code: string;
  name: string;
  flag: string;
  nativeName: string;
}

const LANGUAGES: LanguageOption[] = [
  { code: 'fr', name: 'Français', flag: '🇫🇷', nativeName: 'Français' },
  { code: 'en', name: 'English', flag: '🇬🇧', nativeName: 'English' },
  { code: 'it', name: 'Italiano', flag: '🇮🇹', nativeName: 'Italiano' },
  { code: 'de', name: 'Deutsch', flag: '🇩🇪', nativeName: 'Deutsch' },
  { code: 'ar', name: 'العربية', flag: '🇹🇳', nativeName: 'العربية' },
];

export const LanguageSwitcher: React.FC = () => {
  const { i18n, t } = useTranslation();

  useEffect(() => {
    const isArabic = (i18n.resolvedLanguage || i18n.language || 'fr').startsWith('ar');
    document.documentElement.lang = isArabic ? 'ar' : (i18n.resolvedLanguage || i18n.language || 'fr');
    document.documentElement.dir = isArabic ? 'rtl' : 'ltr';
  }, [i18n.resolvedLanguage, i18n.language]);

  const handleLanguageChange = (languageCode: string) => {
    i18n.changeLanguage(languageCode);
    localStorage.setItem('i18nextLng', languageCode);
  };

  const currentCode = (i18n.resolvedLanguage || i18n.language || 'fr').split('-')[0];

  return (
    <div className="flex items-center gap-2">
      <Select value={currentCode} onValueChange={handleLanguageChange}>
        <SelectTrigger className="w-[160px] flex items-center gap-2" aria-label={t('common.language')}>
          <Globe className="w-4 h-4" />
          <SelectValue placeholder={t('common.language')} />
        </SelectTrigger>
        <SelectContent>
          {LANGUAGES.map((lang) => (
            <SelectItem key={lang.code} value={lang.code}>
              <div className="flex items-center gap-2">
                <span className="text-lg">{lang.flag}</span>
                <span>{lang.nativeName}</span>
              </div>
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
};

export default LanguageSwitcher;
