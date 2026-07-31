// Single source of truth for project icon options (picker + anywhere a
// project_icon name must resolve to a component).
import {
  Folder, FolderKanban, Briefcase, Code2, Palette, BarChart3, PieChart, LineChart,
  Rocket, Target, Wrench, Hammer, Layers, Compass, Cpu, Building2, HardHat, Sparkles,
  Bug, FlaskConical, Zap, Flag, CalendarDays, Megaphone, ShoppingCart, Truck, Package,
  Globe, Users, Heart, Shield, Star, BookOpen, PenTool, Camera, Database, Cloud, Server,
  GitBranch, Smartphone, Monitor, Coffee, Map, Leaf, Factory, Stethoscope, Scale,
  GraduationCap, Banknote, Wallet, Lightbulb, Microscope, Wind, Plane,
} from 'lucide-vue-next'

export const PROJECT_ICON_MAP = {
  Folder, FolderKanban, Briefcase, Code2, Palette, BarChart3, PieChart, LineChart,
  Rocket, Target, Wrench, Hammer, Layers, Compass, Cpu, Building2, HardHat, Sparkles,
  Bug, FlaskConical, Zap, Flag, CalendarDays, Megaphone, ShoppingCart, Truck, Package,
  Globe, Users, Heart, Shield, Star, BookOpen, PenTool, Camera, Database, Cloud, Server,
  GitBranch, Smartphone, Monitor, Coffee, Map, Leaf, Factory, Stethoscope, Scale,
  GraduationCap, Banknote, Wallet, Lightbulb, Microscope, Wind, Plane,
}

export function resolveProjectIcon(name) {
  return PROJECT_ICON_MAP[name] || Folder
}
